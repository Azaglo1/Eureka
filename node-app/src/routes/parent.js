const express = require("express");
const { requireAuth } = require("../middleware/auth");
const { requireRole } = require("../middleware/roles");

const router = express.Router();

router.get("/", requireAuth, requireRole("parent", "admin", "superadmin"), (req, res) => {
  res.render("modules/placeholder", {
    title: "Parent",
    activeNav: "parent",
    moduleName: "Parent",
    moduleDescription: "Children, fees, attendance, results, and messages will move here."
  });
});

module.exports = router;
