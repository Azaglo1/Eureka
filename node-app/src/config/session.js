const session = require("express-session");
const pgSession = require("connect-pg-simple")(session);
const { Pool } = require("pg");
const { env } = require("./env");

function sessionMiddleware() {
  const options = {
    name: "school.sid",
    secret: env.SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: "lax",
      secure: env.NODE_ENV === "production",
      maxAge: 1000 * 60 * 60 * 8
    }
  };

  if (env.NODE_ENV === "production" || env.SESSION_STORE === "postgres") {
    const pgPool = new Pool({
      connectionString: env.DATABASE_URL
    });

    options.store = new pgSession({
      pool: pgPool,
      tableName: "user_sessions",
      createTableIfMissing: true
    });
  }

  return session({
    ...options
  });
}

module.exports = { sessionMiddleware };
