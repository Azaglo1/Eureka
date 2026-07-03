const express = require("express");
const { requireAuth } = require("../middleware/auth");
const { requireRole } = require("../middleware/roles");

const router = express.Router();

router.get("/", requireAuth, requireRole("superadmin"), (req, res) => {
  res.render("modules/placeholder", {
    title: "Super Admin",
    activeNav: "superadmin",
    moduleName: "Super Admin",
    moduleDescription: "School management, global users, imports, statistics, and audit logs will move here."
  });
});

module.exports = router;
