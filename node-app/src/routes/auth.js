const express = require("express");
const authController = require("../controllers/auth.controller");
const { requireAuth } = require("../middleware/auth");

const router = express.Router();

router.get("/", authController.showLogin);
router.post("/", authController.login);
router.post("/logout", requireAuth, authController.logout);
router.get("/logout", requireAuth, authController.logout);

module.exports = router;
