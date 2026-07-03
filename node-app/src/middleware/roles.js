function requireRole(...roles) {
  return (req, res, next) => {
    const role = req.session.user && req.session.user.role;
    if (!role || !roles.includes(role)) {
      req.session.flash = { type: "danger", message: "You do not have permission to access that page." };
      return res.redirect("/dashboard");
    }
    return next();
  };
}

module.exports = { requireRole };
