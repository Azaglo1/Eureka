const bcrypt = require("bcrypt");
const { prisma } = require("../config/prisma");
const { listActiveSchools } = require("../services/school.service");

async function showLogin(req, res) {
  const schools = await listActiveSchools();
  res.render("auth/login", {
    title: "Login",
    layout: "layouts/auth",
    schools
  });
}

async function login(req, res) {
  const schoolCode = (req.body.school_code || "").trim();
  const loginCode = (req.body.login_code || "").trim();

  if (!schoolCode || !loginCode) {
    req.session.flash = { type: "warning", message: "School and access credentials are required." };
    return res.redirect("/");
  }

  try {
    const user = await prisma.user.findFirst({
      where: {
        loginCode,
        active: 1,
        school: {
          schoolCode,
          active: 1
        }
      },
      include: { school: true }
    });

    if (!user) {
      req.session.flash = { type: "danger", message: "Invalid school or access credentials." };
      return res.redirect("/");
    }

    const isBcryptHash = user.passwordHash.startsWith("$2a$") || user.passwordHash.startsWith("$2b$") || user.passwordHash.startsWith("$2y$");
    const passwordMatches = isBcryptHash ? await bcrypt.compare(loginCode, user.passwordHash) : false;

    if (!passwordMatches) {
      req.session.flash = {
        type: "warning",
        message: "This account needs a password reset before it can sign in to the Node.js app."
      };
      return res.redirect("/");
    }

    req.session.user = {
      userId: user.id,
      name: user.name,
      role: user.role,
      schoolId: user.schoolId,
      schoolName: user.school ? user.school.name : null,
      privileges: user.privileges || ""
    };

    return res.redirect("/dashboard");
  } catch (error) {
    console.error(error);
    req.session.flash = { type: "danger", message: "Login is unavailable until the database is connected." };
    return res.redirect("/");
  }
}

function logout(req, res) {
  req.session.destroy(() => {
    res.redirect("/");
  });
}

module.exports = { showLogin, login, logout };
