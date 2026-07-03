# School Project Record System

A comprehensive, modern school management system with role-based access control, designed for seamless administration and communication.

## 🌟 Features

### Core Functionality
- **Role-Based Access Control**: Five distinct user roles with tailored permissions
  - **Super Admin**: Full system control, manage all schools and users
  - **Admin**: School-level administration, manage users and students
  - **Teacher**: Mark attendance, record grades, manage assignments and timetable
  - **Parent**: View children's progress, attendance, grades, and fees
  - **Student**: Access personal academic information

- **Student Management**: Complete enrollment, attendance, and academic tracking
- **Attendance System**: Daily and weekly attendance recording with flexible filtering
- **Grade Recording**: Comprehensive grade management with class ranking
- **Fee Management**: Track billing, payments, and outstanding balances
- **Communication**: Internal messaging system between users
- **Timetable Management**: Class schedules and teacher assignments
- **Library System**: Book catalog and loan tracking
- **Announcements**: Targeted announcements by audience type
- **Event Calendar**: School events and activities
- **Assignment Tracking**: Homework and project assignments

## 🚀 Getting Started

### Prerequisites
- Node.js 20+
- PostgreSQL

### Installation

1. (Optional) Copy `.env.example` to `.env` and customize the configuration:
```bash
copy .env.example .env
```

2. Install dependencies:
```bash
npm install
```

3. Run the Node.js application:
```bash
npm start
```

4. Open `http://127.0.0.1:3000` in your browser for the main portal.

### Super Admin Portal

The super admin portal is now part of the same Express application and is mounted under `/superadmin`.

## 👥 Demo Credentials

| Role | Login Code | Description |
|------|-----------|-------------|
| Super Admin | `superadmin123` | Full system access |
| Admin | `admin123` | School administration |
| Teacher | `teacher123`, `teacher456` | Teaching and grading |
| Parent | `parent123`, `parent456` | View children's progress |
| Student | N/A | Access via parent account |

**School Code**: `SHS001`

## 🎯 User Roles & Permissions

### Super Admin
- Create and manage multiple schools
- Full user management across all schools
- System-wide reporting and analytics
- Complete control over all system features

### Admin (School Head)
- Manage users within their school
- Add, update, and remove students
- Assign teacher privileges
- View all school reports and analytics
- Manage fee structures and billing

### Teacher
- Mark daily attendance
- Record and update student grades
- Create and manage assignments
- Set and update class timetable
- View assigned class information
- Communicate with parents and students

### Parent
- View all enrolled children
- Monitor attendance records
- Track grades and academic progress
- Check fee status and payment history
- Receive announcements and messages
- View class timetable

### Student
- View personal information
- Check grades and attendance
- Access assignments and timetable
- View library loans

## 📊 Database Schema

The system uses SQLite with the following main tables:
- **schools**: School information
- **users**: User accounts with role-based access
- **students**: Student enrollment records
- **attendances**: Daily attendance tracking
- **grades**: Academic performance records
- **fees**: Fee billing and payment tracking
- **messages**: Internal communication system
- **announcements**: School-wide notifications
- **events**: Calendar of school activities
- **assignments**: Homework and project tracking
- **timetable**: Class schedules
- **library_books**: Book catalog
- **book_loans**: Library loan tracking
- **certificates**: Student certificates
- **medical_records**: Health information

## 🎨 Design Philosophy

The system features a modern, clean interface with:
- **Responsive Design**: Works on desktop and mobile devices
- **Intuitive Navigation**: Clear role-based menu structure
- **Visual Hierarchy**: Important information prominently displayed
- **Consistent Styling**: Unified design language throughout
- **Accessibility**: High contrast and clear typography

### Color Scheme
- **Primary**: Blue gradient (#1e40af → #3b82f6)
- **Neutral**: Slate grays for backgrounds and text
- **Status Colors**: Success (green), Warning (amber), Danger (red), Info (blue)
- **Role Colors**: Distinct colors for each user role

## 🔧 Technical Stack

- **Backend**: Node.js, Express.js
- **Database**: PostgreSQL
- **ORM**: Prisma
- **Frontend**: EJS, HTML5, CSS3, JavaScript
- **Styling**: Bootstrap and custom CSS
- **Authentication**: Session-based with password hashing

## 📁 Project Structure

```
school/
├── package.json           # Root Node.js scripts
├── package-lock.json      # Root install lockfile
├── Procfile               # Production process entry
├── node-app/
│   ├── package.json       # Express app dependencies and scripts
│   ├── server.js          # Node entry point
│   ├── prisma/
│   │   ├── schema.prisma  # Prisma database schema
│   │   └── seed.js        # Prisma seed script
│   └── src/
│       ├── app.js         # Express app setup
│       ├── config/        # Environment, Prisma, and session config
│       ├── controllers/   # Request handlers
│       ├── middleware/    # Auth, roles, and school scoping
│       ├── routes/        # Role-prefixed route modules
│       ├── services/      # Business logic
│       ├── views/         # EJS templates
│       └── public/        # Static assets
├── app.py                 # Legacy Flask reference
├── superadmin_app.py      # Legacy Flask superadmin reference
├── static/                # Legacy Flask static assets
└── templates/             # Legacy Flask Jinja templates
```

## 🛡️ Security Features

- Password hashing with bcrypt
- Session-based authentication
- Role-based access control
- SQL injection prevention through Prisma queries
- CSRF protection (basic)
- Input validation

## 🚀 Future Enhancements

- [ ] SMS/Email notifications
- [ ] Parent-teacher conference scheduling
- [ ] Exam management system
- [ ] Report card generation
- [ ] Mobile application
- [ ] Multi-school support
- [ ] Advanced reporting and analytics
- [ ] File upload system for assignments
- [ ] Video conferencing integration
- [ ] Offline capability with service workers

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Built for educational institutions seeking digital transformation
- Designed with teachers, parents, and students in mind
- Inspired by the need for better school-home communication

