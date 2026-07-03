const express = require("express");
const { requireAuth } = require("../middleware/auth");
const { requireRole } = require("../middleware/roles");

const router = express.Router();

router.get("/", requireAuth, requireRole("accountant", "admin", "superadmin"), (req, res) => {
  res.render("modules/placeholder", {
    title: "Accountant",
    activeNav: "accountant",
    moduleName: "Accountant",
    moduleDescription: "Invoices, payments, balances, and finance reports will move here."
  });
});

module.exports = router;
