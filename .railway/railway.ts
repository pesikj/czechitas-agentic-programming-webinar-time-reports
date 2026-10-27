import { defineRailway, github, project, service } from "railway/iac";
// This repository manages only its own resources in the environment. Other
// repositories export their own partial name.
// See https://docs.railway.com/infrastructure-as-code#multi-repo-projects
export const partial = "web";
export default defineRailway((ctx) => {
  const web = service("web", {
    source: github("pesikj/czechitas-agentic-programming-webinar-time-reports", {
      branch: ctx.isEnvironment("test") ? "test" : "main",
      checkSuites: true,
    }),
    build: { buildEnvironment: "V3" },
    healthcheck: "/health/",
    healthcheckTimeout: 120,
    preDeploy: "python manage.py migrate --noinput",
    replicas: { "ams": 1 },
  });

  return project("czechitas-time-reports", {
    variables: { managed: false },
    resources: [web],
  });
});
