const express = require("express");
const { showDashboard } = require("../controllers/dashboard.controller");
const { requireAuth } = require("../middleware/auth");
const { requireSchoolScope } = require("../middleware/schoolScope");

const router = express.Router();

router.get("/dashboard", requireAuth, requireSchoolScope, showDashboard);

module.exports = router;
