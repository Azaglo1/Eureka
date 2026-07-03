const express = require("express");
const { checkDatabase } = require("../config/prisma");

const router = express.Router();

router.get("/health", async (req, res) => {
  const status = {
    app: "ok",
    database: "unknown"
  };

  try {
    await checkDatabase();
    status.database = "ok";
  } catch (error) {
    status.database = "unavailable";
    status.databaseError = error.message;
  }

  res.json(status);
});

module.exports = router;
