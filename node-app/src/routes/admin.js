const express = require("express");
const { requireAuth } = require("../middleware/auth");
const { requireRole } = require("../middleware/roles");

const router = express.Router();

router.get("/", requireAuth, requireRole("admin", "superadmin"), (req, res) => {
  res.render("modules/placeholder", {
    title: "Admin",
    activeNav: "admin",
    moduleName: "Admin",
    moduleDescription: "Students, teachers, classes, subjects, and school settings will move here."
  });
});

module.exports = router;
