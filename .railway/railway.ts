import { defineRailway, project, service } from "railway/iac";
// This repository manages only its own resources in the environment. Other
// repositories export their own partial name.
// See https://docs.railway.com/infrastructure-as-code#multi-repo-projects
export const partial = "web";
export default defineRailway(() => {
  const web = service("web", {
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
