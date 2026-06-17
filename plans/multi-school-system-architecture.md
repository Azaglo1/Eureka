# Multi-School System Architecture Plan

## Current State Analysis

### Existing Infrastructure ✅
The system already has a solid multi-school foundation:

1. **Database Schema** - All tables include `school_id` foreign key:
   - `schools` table (id, name, school_code, description)
   - `users` (school_id)
   - `students` (school_id)
   - `attendances` (school_id)
   - `grades` (school_id)
   - `fees` (school_id)
   - `messages` (school_id)
   - `announcements` (school_id)
   - `events` (school_id)
   - `assignments` (school_id)
   - `timetable` (school_id)
   - `library_books` (school_id)
   - `book_loans` (school_id)
   - `certificates` (school_id)
   - `medical_records` (school_id)
   - `teaching_plans` (school_id)
   - `teacher_assignments` (school_id)

2. **Authentication & Authorization**:
   - Login with school_code selection
   - Session stores `school_id`, `school_name`, `school_code`
   - Role-based access control (superadmin, admin, teacher, parent, student)
   - All queries filter by `school_id` from session

3. **Existing Routes**:
   - `POST /admin/create_school` - Creates new school (superadmin only)
   - `GET /superadmin/school/<school_id>` - Placeholder test route
   - `POST /superadmin/update_user_school` - Assigns users to schools
   - `POST /superadmin/remove_user_school/<user_id>` - Removes user from school

### Issues Identified ❌
1. **School Portal is Non-Functional**: Route returns plain text "test to see if the route works"
2. **Template Exists But Not Used**: `templates/school_portal.html` exists but isn't properly rendered
3. **No School-Specific Dashboard**: Each school needs its own dedicated management interface
4. **Limited School Management**: Only school creation exists; no edit/delete/management features
5. **No School Branding**: All schools look identical; no customization options
6. **Missing School Navigation**: No way to switch between schools as superadmin

---

## Proposed Architecture Enhancements

### Phase 1: Core School Portal (Immediate)
**Goal**: Make each school have its own functional portal with real data

#### 1.1 Update `superadmin_school_portal` Route
**File**: `app.py`
**Changes**:
- Query school details by `school_id`
- Calculate school-specific statistics:
  - Total students (active)
  - Total teachers (users with role='teacher')
  - Total admins (users with role='admin')
  - Today's attendance count
  - Recent activity (latest grades, announcements, events)
- Render `school_portal.html` template with all data
- Add access control: superadmin only, or optionally allow school admins to view their own school

#### 1.2 Enhance `school_portal.html` Template
**File**: `templates/school_portal.html`
**Improvements**:
- Display school name, code, and description prominently
- Show statistics in attractive cards with icons
- Add quick action buttons (View Students, View Teachers, View Attendance, etc.)
- Show recent announcements and events for that school
- Add school-specific navigation or breadcrumb
- Include "Back to All Schools" button for superadmin
- Make it visually distinct with school-specific styling (if we add school colors later)

#### 1.3 Add School Management Actions
**New Routes** (in `app.py`):
- `GET /admin/school/<int:school_id>/edit` - Show edit form
- `POST /admin/school/<int:school_id>/edit` - Update school details
- `POST /admin/school/<int:school_id>/delete` - Soft-delete school (set inactive)
- `GET /admin/school/<int:school_id>/users` - List all users for that school
- `GET /admin/school/<int:school_id>/students` - List all students for that school

**New Template**:
- `templates/edit_school.html` - Form to edit school name, code, description

### Phase 2: School-Specific Admin Experience
**Goal**: Allow school admins to manage their own school independently

#### 2.1 School Admin Dashboard
**New Route**: `GET /admin/school_dashboard`
- Shows only data for `session['school_id']`
- School-specific statistics and quick actions
- Recent activity within that school
- Pending tasks (unread messages, pending fees, etc.)

#### 2.2 Enhanced Admin Panel Filtering
**File**: `templates/admin.html` & `app.py` admin routes
- All admin actions already filter by `school_id`
- Add clear visual indicator of which school admin is managing
- Add school selector for superadmin when viewing admin panel (to filter by school)

#### 2.3 School-Specific Reports
**New Routes**:
- `GET /admin/school/<int:school_id>/reports/attendance` - Attendance reports
- `GET /admin/school/<int:school_id>/reports/academic` - Academic performance
- `GET /admin/school/<int:school_id>/reports/financial` - Financial summary

### Phase 3: School Branding & Customization (Optional)
**Goal**: Allow each school to have its own visual identity

#### 3.1 Extend `schools` Table
Add columns:
- `logo_url` TEXT - School logo image URL
- `primary_color` VARCHAR(20) - Brand color (hex)
- `secondary_color` VARCHAR(20) - Secondary brand color
- `address` TEXT - Physical address
- `phone` TEXT - Contact phone
- `email` TEXT - School email
- `website` TEXT - School website
- `motto` TEXT - School motto

#### 3.2 Update Templates
- Use school branding colors in headers/badges when viewing that school
- Display school logo in sidebar (next to school name or in header)
- Apply school-specific theme colors throughout the interface

#### 3.3 School Settings Page
**New Route**: `GET /admin/school/settings`
- Allow school admins to update their school's information
- Upload/change logo
- Set brand colors
- Update contact details

### Phase 4: Advanced Multi-School Features
**Goal**: Enable cross-school collaboration while maintaining data isolation

#### 4.1 School Groups/Networks
- Allow superadmin to group schools into networks/districts
- Share announcements across multiple schools
- Compare performance across schools in same network

#### 4.2 Inter-School Messaging
- Allow admins/teachers to send messages to users in other schools (with permission)
- Maintain privacy and data isolation

#### 4.3 System-Wide vs School-Specific Content
- Distinguish between superadmin announcements (system-wide) and school-specific announcements
- Filter events and messages appropriately

---

## Implementation Order

### Sprint 1: Functional School Portal (Week 1)
1. Fix `superadmin_school_portal` route to render template with real data
2. Enhance `school_portal.html` with statistics and quick actions
3. Add school edit/delete functionality for superadmin
4. Test with multiple schools

### Sprint 2: School Admin Independence (Week 2)
1. Create school-specific admin dashboard
2. Add school management tools for admins (user creation, student management)
3. Improve admin panel UI to show current school context
4. Add school-specific reports

### Sprint 3: Branding & Polish (Week 3)
1. Add school branding fields to database
2. Create school settings page
3. Update UI to use school colors/logo
4. Improve overall user experience

### Sprint 4: Advanced Features (Week 4+)
1. School groups/networks
2. Inter-school messaging
3. System-wide vs school-specific content filtering
4. Advanced analytics and reporting

---

## Technical Considerations

### Security
- All queries MUST filter by `school_id` from session
- Superadmin can access any school; regular users only their own
- Validate that requested school_id matches user's school (for non-superadmin)
- Prevent SQL injection (already using parameterized queries)

### Performance
- Add database indexes on `school_id` columns (likely already exists)
- Cache school statistics if needed
- Use efficient queries with proper joins

### User Experience
- Clear visual indication of which school you're viewing/managing
- Easy navigation between schools for superadmin
- Consistent branding within each school's context
- Mobile-responsive design

---

## Database Migration Notes

The current schema already supports multi-school. No migrations needed for Phase 1.

For Phase 3 (branding), add columns to `schools` table:
```sql
ALTER TABLE schools ADD COLUMN logo_url TEXT;
ALTER TABLE schools ADD COLUMN primary_color VARCHAR(20);
ALTER TABLE schools ADD COLUMN secondary_color VARCHAR(20);
ALTER TABLE schools ADD COLUMN address TEXT;
ALTER TABLE schools ADD COLUMN phone TEXT;
ALTER TABLE schools ADD COLUMN email TEXT;
ALTER TABLE schools ADD COLUMN website TEXT;
ALTER TABLE schools ADD COLUMN motto TEXT;
```

---

## Success Criteria

### Phase 1 Completion
- [ ] Superadmin can click on a school card and see a detailed portal
- [ ] Portal displays accurate statistics (students, teachers, attendance)
- [ ] Portal shows recent announcements, events, and activity
- [ ] Quick action buttons navigate to appropriate pages
- [ ] Superadmin can edit school details
- [ ] Superadmin can delete/deactivate schools
- [ ] All data is properly isolated by school

### Phase 2 Completion
- [ ] School admins see their own school dashboard
- [ ] All admin actions are clearly scoped to their school
- [ ] School admins can manage their users and students
- [ ] Reports show only school-specific data

### Phase 3 Completion
- [ ] Schools can upload logos and set brand colors
- [ ] UI reflects school branding when logged into that school
- [ ] School settings page works for admins

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data leakage between schools | Critical | Strict `school_id` checks in all queries; thorough testing |
| Performance degradation with many schools | High | Database indexing; query optimization; caching |
| Complex UI for superadmin managing many schools | Medium | Pagination; search/filter; school grouping |
| Migration issues with existing single-school data | Medium | Backup database; test migration on copy first |

---

## Conclusion

The system already has excellent multi-school **data isolation** through `school_id` foreign keys. The main gap is the **user interface** - there's no proper school portal or management interface. This plan addresses that by:

1. **Activating** the dormant `school_portal.html` template
2. **Creating** a functional school management dashboard
3. **Enhancing** the superadmin experience for multi-school oversight
4. **Laying groundwork** for school-specific branding and customization

The implementation can proceed incrementally with each sprint delivering value while maintaining system stability.
