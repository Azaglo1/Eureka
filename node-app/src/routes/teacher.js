const express = require("express");
const { requireAuth } = require("../middleware/auth");
const { requireRole } = require("../middleware/roles");

const router = express.Router();

router.get("/", requireAuth, requireRole("teacher", "admin", "superadmin"), (req, res) => {
  res.render("modules/placeholder", {
    title: "Teacher",
    activeNav: "teacher",
    moduleName: "Teacher",
    moduleDescription: "Attendance, assignments, teaching plans, and results will move here."
  });
});

module.exports = router;
