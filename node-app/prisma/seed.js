const { PrismaClient } = require("@prisma/client");

const prisma = new PrismaClient();

async function main() {
  const school = await prisma.school.upsert({
    where: { schoolCode: "SHS001" },
    update: {},
    create: {
      name: "Sample School",
      schoolCode: "SHS001",
      description: "Seed school for local Node.js development.",
      active: 1
    }
  });

  console.log(`Seeded school: ${school.name} (${school.schoolCode})`);
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
