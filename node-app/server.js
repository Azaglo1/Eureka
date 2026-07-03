const app = require("./src/app");
const { env } = require("./src/config/env");

const server = app.listen(env.PORT, () => {
  console.log(`School Node app running on http://localhost:${env.PORT}`);
});

function shutdown(signal) {
  console.log(`${signal} received. Closing HTTP server.`);
  server.close(() => {
    process.exit(0);
  });
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
