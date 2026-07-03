const path = require("path");
const express = require("express");
const expressLayouts = require("express-ejs-layouts");
const helmet = require("helmet");
const compression = require("compression");
const rateLimit = require("express-rate-limit");

const { env } = require("./config/env");
const { sessionMiddleware } = require("./config/session");
const { attachLocals } = require("./middleware/auth");

const authRoutes = require("./routes/auth");
const dashboardRoutes = require("./routes/dashboard");
const adminRoutes = require("./routes/admin");
const teacherRoutes = require("./routes/teacher");
const studentRoutes = require("./routes/student");
const parentRoutes = require("./routes/parent");
const accountantRoutes = require("./routes/accountant");
const superAdminRoutes = require("./routes/superadmin");
const healthRoutes = require("./routes/health");

const app = express();

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));
app.set("layout", "layouts/main");

app.use(helmet({ contentSecurityPolicy: false }));
app.use(compression());
app.use(expressLayouts);
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use("/assets", express.static(path.join(__dirname, "public")));
app.use("/vendor/bootstrap", express.static(path.join(__dirname, "../node_modules/bootstrap/dist")));

app.use(
  rateLimit({
    windowMs: 15 * 60 * 1000,
    limit: env.NODE_ENV === "production" ? 100 : 1000,
    standardHeaders: "draft-7",
    legacyHeaders: false
  })
);

app.use(sessionMiddleware());
app.use(attachLocals);
app.use((req, res, next) => {
  res.locals.activeNav = "";
  next();
});

app.use(healthRoutes);
app.use("/", authRoutes);
app.use(dashboardRoutes);
app.use("/admin", adminRoutes);
app.use("/teacher", teacherRoutes);
app.use("/student", studentRoutes);
app.use("/parent", parentRoutes);
app.use("/accountant", accountantRoutes);
app.use("/superadmin", superAdminRoutes);

app.use((req, res) => {
  res.status(404).render("errors/404", { title: "Not Found" });
});

app.use((error, req, res, next) => {
  console.error(error);
  res.status(500).render("errors/500", {
    title: "Server Error",
    error: env.NODE_ENV === "development" ? error : null
  });
});

module.exports = app;
