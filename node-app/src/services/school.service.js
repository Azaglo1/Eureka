const { prisma } = require("../config/prisma");

async function listActiveSchools() {
  try {
    return await prisma.school.findMany({
      where: { active: 1 },
      orderBy: { name: "asc" },
      select: { id: true, name: true, schoolCode: true }
    });
  } catch (error) {
    console.warn(`Could not load schools from database: ${error.message}`);
    return [
      {
        id: 1,
        name: "Sample School",
        schoolCode: "SHS001"
      }
    ];
  }
}

module.exports = { listActiveSchools };
