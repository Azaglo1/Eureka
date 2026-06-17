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
- Python 3.7+
- SQLite3 (included with Python)

### Installation

1. (Optional) Copy `.env.example` to `.env` and customize the configuration:
```bash
copy .env.example .env
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the main application:
```bash
python app.py
```

3. Open `http://127.0.0.1:5000` in your browser for the main portal

### Super Admin Portal

The super admin portal runs as a separate Flask application:

```bash
python superadmin_app.py
```

By default, it runs on `http://127.0.0.1:8080`. You can change the port using the `SUPERADMIN_PORT` environment variable:

```bash
# On Windows (cmd)
set SUPERADMIN_PORT=5002 && python superadmin_app.py

# On Linux/Mac
SUPERADMIN_PORT=5002 python superadmin_app.py
```

Or in PowerShell:
```powershell
$env:SUPERADMIN_PORT=5002; python superadmin_app.py
```

The super admin login is available at: `http://127.0.0.1:8080/superadmin/login`

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

- **Backend**: Flask (Python)
- **Database**: SQLite
- **Frontend**: HTML5, CSS3, JavaScript
- **Styling**: Custom CSS with CSS3 features
- **Authentication**: Session-based with password hashing

## 📁 Project Structure

```
school/
├── app.py                 # Main Flask application (port 5000)
├── superadmin_app.py      # Super admin Flask application (port 8080)
├── school.db              # SQLite database
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── static/
│   └── style.css         # Application styles
└── templates/
    ├── base.html         # Base template
    ├── login.html        # Login page
    ├── dashboard.html    # Main dashboard
    ├── admin.html        # Admin panel
    ├── superadmin.html   # Super admin panel
    ├── attendance.html   # Attendance management
    ├── grades.html       # Grade recording
    ├── timetable.html    # Class schedules
    ├── assignments.html  # Assignment tracking
    ├── events.html       # Event calendar
    ├── announcements.html # Announcements
    ├── library.html      # Library catalog
    ├── messages.html     # Messaging system
    ├── finance.html      # Fee management
    ├── parent.html       # Parent dashboard
    └── students.html     # Student directory
```

## 🛡️ Security Features

- Password hashing with Werkzeug
- Session-based authentication
- Role-based access control
- SQL injection prevention
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
