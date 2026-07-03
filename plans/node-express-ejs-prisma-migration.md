# Node/Express Migration Plan

## Recommended Stack

Use this stack for the first Node.js version:

| Layer | Choice | Reason |
| --- | --- | --- |
| Runtime | Node.js | Broad hosting support and easy deployment on Hostinger-style VPS plans. |
| Web framework | Express.js | Simple match for the current Flask route/controller style. |
| Views | EJS | Closest migration path from the current Jinja templates in `templates/`. |
| UI framework | Bootstrap | Fastest way to rebuild server-rendered pages consistently. |
| Database | PostgreSQL | The current production docs and `db_utils.py` already support PostgreSQL. |
| ORM | Prisma | Typed schema, migrations, relations, and future MySQL provider swap if needed. |
| Auth | Sessions + bcrypt | Best fit for server-rendered EJS pages. JWT can be added later for APIs. |
| Uploads | Multer | Handles library files, assignment attachments, teaching-plan files, audio, and cover images. |
| Email | Nodemailer | Replaces SMTP helpers in `app.py`. |
| PDF | Puppeteer | Best fit because current reports are HTML-based before PDF generation. |
| Excel/CSV | ExcelJS | Replaces CSV import/export and supports richer import templates. |

PostgreSQL should be the default. Use MySQL only if the chosen Hostinger plan gives managed MySQL but not PostgreSQL. Prisma can switch providers later, but PostgreSQL is a better fit for the existing production guide.

## Current App Shape

The existing app is a Flask/Jinja school management system with:

- Main portal in `app.py`
- Superadmin portal in `superadmin_app.py`
- Shared DB helper in `db_utils.py`
- Server-rendered pages in `templates/`
- Static assets in `static/`
- Local uploads under `static/uploads/`
- Temporary exports under `temp_exports/`
- Multi-school scoping through `school_id`
- Roles: `superadmin`, `admin`, `teacher`, `parent`, `student`

The Node version should preserve server-rendered pages first. A React frontend can come later after the backend is stable.

Do not translate Flask to Express line by line. Use the existing Flask code as the functional specification, then rebuild each feature with Express best practices. That produces a cleaner codebase instead of carrying over old route structure, query duplication, and accumulated technical debt.

## Target Project Structure

```text
node-app/
  package.json
  .env.example
  prisma/
    schema.prisma
    migrations/
    seed.js
  src/
    server.js
    app.js
    config/
      env.js
      prisma.js
      upload.js
    middleware/
      auth.js
      roles.js
      schoolScope.js
      validation.js
    routes/
      auth.js
      admin.js
      teacher.js
      student.js
      parent.js
      accountant.js
      superadmin.js
    controllers/
    repositories/
    services/
      auth.service.js
      email.service.js
      sms.service.js
      whatsapp.service.js
      report.service.js
      upload.service.js
    views/
      layouts/
      partials/
      *.ejs
    public/
      css/
      js/
      uploads/
```

Keep the Node app in a separate `node-app/` folder during migration so the Flask app remains runnable until feature parity is reached.

Use one Express application, not two separate Node servers. Preserve role separation through route prefixes:

```js
app.use("/", authRoutes);
app.use("/admin", adminRoutes);
app.use("/teacher", teacherRoutes);
app.use("/student", studentRoutes);
app.use("/parent", parentRoutes);
app.use("/accountant", accountantRoutes);
app.use("/superadmin", superAdminRoutes);
```

This replaces the current `app.py` and `superadmin_app.py` split while keeping permissions and responsibilities easy to reason about.

## Package Baseline

Core dependencies:

```bash
npm install express ejs express-ejs-layouts dotenv @prisma/client bcrypt express-session connect-pg-simple multer nodemailer exceljs puppeteer helmet compression express-rate-limit zod bootstrap
npm install -D prisma nodemon eslint prettier
```

Use `express-session` with `connect-pg-simple` so sessions are stored in PostgreSQL instead of process memory. This fits Hostinger/VPS deployment better and matches the current server-rendered app flow.

Hostinger-ready `package.json` scripts:

```json
{
  "scripts": {
    "start": "node server.js",
    "dev": "nodemon server.js"
  }
}
```

Baseline `.env` keys:

```env
DATABASE_URL=
SESSION_SECRET=
SMTP_HOST=
SMTP_PORT=
SMTP_USER=
SMTP_PASS=
WHATSAPP_TOKEN=
```

## Authentication Design

Current Flask behavior:

- Login uses `school_code` and `login_code`.
- Password validation uses Werkzeug hash checks.
- Session stores `user_id`, `user_name`, `role`, `privileges`, `school_id`, `school_name`, and `school_code`.

Node target:

- Use `bcrypt` for new password hashes.
- Use server-side sessions stored in PostgreSQL.
- Session data should include only stable authorization claims:
  - `userId`
  - `role`
  - `schoolId`
  - `privileges`
- Load fresh user and school details from Prisma when needed.
- Keep `school_id` authorization checks centralized in `schoolScope` middleware.

Important migration note: existing Werkzeug hashes cannot be verified by bcrypt. Use a transition flow:

1. Add a `password_hash_algorithm` column, or infer by hash prefix.
2. During first successful login in Flask, ask users to reset password before Node cutover; or
3. Bulk reset login codes/passwords and notify admins; or
4. Temporarily keep Flask auth for old users until all accounts are migrated.

Option 2 is the cleanest for a real school system.

## Prisma Schema Starting Point

Start by introspecting the production PostgreSQL database:

```bash
npx prisma init
npx prisma db pull
npx prisma generate
```

Then normalize model names and relations. Expected core models:

- `School`
- `User`
- `Role`
- `Student`
- `Teacher`
- `Parent`
- `Class`
- `Subject`
- `Enrollment`
- `Attendance`
- `Exam`
- `Result`
- `Grade`
- `Invoice`
- `Payment`
- `Message`
- `Announcement`
- `Notification`
- `AuditLog`
- `Event`
- `Assignment`
- `TimetableEntry`
- `LibraryBook`
- `BookLoan`
- `TeachingPlan`
- `TeacherAssignment`
- `SchoolSection`
- `SchoolGradeLevel`
- `SchoolSubject`
- `SchoolClassSubject`
- `StudentReport`

Every school-owned table must keep a required `schoolId` relation except global superadmin data.

## Route Migration Map

| Flask area | Express route file |
| --- | --- |
| `/`, `/logout` | `auth.js` |
| `/admin/*` | `admin.js` |
| `/teacher/*` | `teacher.js` |
| `/student/*` | `student.js` |
| `/parent/*` | `parent.js` |
| `/accountant/*` | `accountant.js` |
| `/superadmin/*`, `/init` | `superadmin.js` |

Within each role route, mount controllers by module: dashboard, students, teachers, classes, subjects, attendance, results, fees, reports, announcements, and messages.

## Template Migration

Jinja to EJS changes are mostly mechanical:

- `{% extends "base.html" %}` becomes EJS layouts.
- `{% include "..." %}` becomes `<%- include("...") %>`.
- `{{ value }}` becomes `<%= value %>`.
- `{{ html|safe }}` becomes `<%- html %>`.
- `{% if condition %}` becomes `<% if (condition) { %>`.
- `{% for item in items %}` becomes `<% items.forEach((item) => { %>`.
- `url_for("route")` should become literal route paths or helper functions.
- Flask `flash()` should become an Express flash helper stored in cookie/session or locals.

Keep `static/style.css` as the first CSS baseline by copying it into `node-app/src/public/css/style.css`.

## Upload Migration

Map existing folders:

- Book files: `static/uploads/`
- Audio: `static/uploads/audio/`
- Covers: `static/uploads/covers/`
- Temporary reports: `temp_exports/`

Multer policies:

- Restrict extensions as the Flask app does.
- Generate server-side filenames, never trust original names.
- Store original filename in DB separately.
- Use per-school subfolders if possible: `uploads/schools/:schoolId/...`.

## Reports

Use Puppeteer for PDF generation because current report code builds HTML documents.

Suggested service:

- `report.service.js`
  - `renderGradeReportHtml(data)`
  - `createGradeReportPdf(data)`
  - `createGradeReportDocHtml(data)`
  - `createExcelExport(rows, columns)`

Use ExcelJS for grade templates, bulk imports, attendance exports, and finance reports.

## Email, SMS, And WhatsApp

Move these helpers into service modules:

- `email.service.js`: Nodemailer SMTP transport
- `sms.service.js`: Twilio or generic provider
- `whatsapp.service.js`: WhatsApp Business API

School-specific SMTP and messaging credentials already exist on `schools`, so service functions should accept `schoolId`, load the school config, then fall back to global `.env` values.

## Security Rules To Preserve

- Every school-owned query must filter by `schoolId`.
- Superadmin can cross school boundaries; other roles cannot.
- Validate uploaded file type and size.
- Use an HTTP-only session cookie.
- Set `helmet()`, rate limits on login, and secure cookie flags in production.
- Never send password hashes, SMTP passwords, Twilio tokens, or WhatsApp tokens to views.
- Audit all superadmin actions that modify schools or users.

## Migration Phases

### Phase 1: Foundation

- Create the Node.js application.
- Add Express, EJS, Bootstrap, Prisma, and PostgreSQL connection.
- Add layout templates, partials, static asset handling, and global error pages.
- Add PostgreSQL-backed session management.
- Add authentication middleware and role middleware.
- Add environment configuration for Hostinger deployment.

At the end of this phase, the Node app should start successfully and render the login page.

### Phase 2: Core Modules

Migrate one module at a time. At the end of each module, the Node version should be runnable and testable.

Recommended order:

1. Authentication
2. Dashboard
3. Students
4. Teachers
5. Classes
6. Subjects
7. Attendance
8. Results
9. Fees
10. Reports

Each module should include its routes, controllers, services, Prisma queries, views, validation, permissions, and basic smoke tests before moving to the next module.

### Phase 3: Advanced Features

- File uploads with Multer.
- PDF generation with Puppeteer.
- Excel imports/exports with ExcelJS.
- Email with Nodemailer.
- SMS provider integration.
- WhatsApp Business integration.
- Notifications.
- Audit logs.

### Phase 4: Super Admin

- Merge the current main and superadmin Flask responsibilities into one Express app.
- Mount superadmin functionality under `/superadmin`.
- Add school management, user management, statistics, imports, and cleanup tools.
- Add audit logging for all superadmin changes.
- Confirm that superadmin can cross school boundaries while every other role stays scoped to one school.

### Phase 5: Cutover And Deployment

- Run Flask and Node against a staging database.
- Compare key pages for each role.
- Freeze writes briefly.
- Migrate/reset passwords.
- Point production traffic to Node.
- Keep Flask available internally for rollback until the school confirms parity.
- Deploy with Hostinger's Node.js workflow using `npm start`, `.env`, and a production PostgreSQL `DATABASE_URL`.

## First Implementation Milestone

The first useful Node milestone should include:

- `GET /` login page rendered with EJS
- `POST /` login with school code and login code/password
- PostgreSQL-backed session creation
- `GET /dashboard`
- `GET /logout`
- Prisma connection to PostgreSQL
- Role middleware
- School scope middleware

That small slice proves the stack without risking the rest of the school workflow.
