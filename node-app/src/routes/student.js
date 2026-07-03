const express = require("express");
const { requireAuth } = require("../middleware/auth");
const { requireRole } = require("../middleware/roles");

const router = express.Router();

router.get("/", requireAuth, requireRole("student", "admin", "superadmin"), (req, res) => {
  res.render("modules/placeholder", {
    title: "Student",
    activeNav: "student",
    moduleName: "Student",
    moduleDescription: "Student profile, attendance, assignments, and results will move here."
  });
});

module.exports = router;
