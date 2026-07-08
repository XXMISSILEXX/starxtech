# Database Schema — PostgreSQL

## 1. users

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('SUPER_ADMIN', 'VIEWER_ADMIN', 'REPORTER')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);
```

## 2. projects

```sql
CREATE TABLE projects (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    start_date DATE NULL,
    expected_end_date DATE NULL,
    created_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);
```

## 3. project_users

```sql
CREATE TABLE project_users (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_in_project VARCHAR(50) NOT NULL DEFAULT 'REPORTER',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, user_id)
);
```

## 4. report_categories

```sql
CREATE TABLE report_categories (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT NULL,
    icon VARCHAR(50) NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP NULL,
    UNIQUE(project_id, name)
);
```

## 5. daily_reports

```sql
CREATE TABLE daily_reports (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    overall_status VARCHAR(50) NOT NULL CHECK (overall_status IN ('UPDATED', 'GOOD', 'PROCESSING', 'ATTENTION', 'CRITICAL')),
    highlight TEXT NOT NULL,
    summary_note TEXT NULL,
    created_by_user_id BIGINT NOT NULL REFERENCES users(id),
    updated_by_user_id BIGINT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP NULL,
    UNIQUE(project_id, report_date)
);
```

## 6. daily_report_sections

```sql
CREATE TABLE daily_report_sections (
    id BIGSERIAL PRIMARY KEY,
    daily_report_id BIGINT NOT NULL REFERENCES daily_reports(id) ON DELETE CASCADE,
    report_category_id BIGINT NOT NULL REFERENCES report_categories(id),
    status VARCHAR(50) NOT NULL CHECK (status IN ('INFO', 'GOOD', 'PROCESSING', 'ATTENTION', 'CRITICAL')),
    content TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(daily_report_id, report_category_id)
);
```

## 7. report_attachments

```sql
CREATE TABLE report_attachments (
    id BIGSERIAL PRIMARY KEY,
    daily_report_section_id BIGINT NOT NULL REFERENCES daily_report_sections(id) ON DELETE CASCADE,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size BIGINT NOT NULL,
    image_width INTEGER NULL,
    image_height INTEGER NULL,
    uploaded_by_user_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);
```

## 8. persistent_issues

```sql
CREATE TABLE persistent_issues (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT NULL,
    severity VARCHAR(50) NOT NULL DEFAULT 'MEDIUM' CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'PROCESSING', 'RESOLVED', 'CLOSED')),
    opened_date DATE NOT NULL,
    due_date DATE NULL,
    closed_date DATE NULL,
    owner_user_id BIGINT NULL REFERENCES users(id),
    created_by_user_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);
```

## 9. audit_logs

```sql
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id BIGINT NULL REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id BIGINT NULL,
    old_values_json JSONB NULL,
    new_values_json JSONB NULL,
    ip_address VARCHAR(100) NULL,
    user_agent TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

## 10. Index khuyến nghị

```sql
CREATE INDEX idx_daily_reports_project_date ON daily_reports(project_id, report_date DESC);
CREATE INDEX idx_daily_reports_status ON daily_reports(overall_status);
CREATE INDEX idx_issues_project_status ON persistent_issues(project_id, status);
CREATE INDEX idx_attachments_section ON report_attachments(daily_report_section_id);
CREATE INDEX idx_project_users_user ON project_users(user_id);
```
