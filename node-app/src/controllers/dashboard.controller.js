function showDashboard(req, res) {
  res.render("dashboard/index", {
    title: "Dashboard",
    activeNav: "dashboard"
  });
}

module.exports = { showDashboard };
