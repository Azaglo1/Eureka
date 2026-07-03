function requireSchoolScope(req, res, next) {
  if (!req.session.user || req.session.user.role === "superadmin" || req.session.user.schoolId) {
    return next();
  }

  req.session.flash = {
    type: "danger",
    message: "Your account is not assigned to a school."
  };
  return res.redirect("/");
}

module.exports = { requireSchoolScope };
