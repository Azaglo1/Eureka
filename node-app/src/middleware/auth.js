function attachLocals(req, res, next) {
  res.locals.currentUser = req.session.user || null;
  res.locals.flash = req.session.flash || null;
  delete req.session.flash;
  next();
}

function requireAuth(req, res, next) {
  if (!req.session.user) {
    req.session.flash = { type: "warning", message: "Please sign in to continue." };
    return res.redirect("/");
  }
  return next();
}

module.exports = { attachLocals, requireAuth };
