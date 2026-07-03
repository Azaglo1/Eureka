const { PrismaClient } = require("@prisma/client");

const prisma = new PrismaClient({
  log: process.env.NODE_ENV === "development" ? ["warn", "error"] : ["error"]
});

async function checkDatabase() {
  await prisma.$queryRaw`SELECT 1`;
  return true;
}

module.exports = { prisma, checkDatabase };
