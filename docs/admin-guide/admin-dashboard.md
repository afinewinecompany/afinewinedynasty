# Administrator Dashboard Guide

## Overview

The Administrator Dashboard provides comprehensive tools for managing the A Fine Wine Dynasty platform, including user management, subscription oversight, content moderation, and system health monitoring.

## Access Requirements

### Admin Roles
- **Super Admin**: Full system access, user management, billing
- **Content Admin**: Prospect data, rankings, content management
- **Support Admin**: User support, ticket management
- **Analytics Admin**: Reports, metrics, business intelligence

### Accessing the Dashboard
1. Navigate to `/admin` or click "Admin" in the main navigation
2. Authenticate with admin credentials
3. Complete 2FA verification (required for all admin accounts)

## Dashboard Sections

### 1. Overview Dashboard

#### Key Metrics Panel
- **Active Users**: Current logged-in users
- **Daily Active Users (DAU)**: Unique users in last 24 hours
- **Monthly Recurring Revenue (MRR)**: Current subscription revenue
- **Churn Rate**: Monthly cancellation percentage
- **System Health**: Overall platform status

#### Quick Actions
- View recent signups
- Process pending support tickets
- Review flagged content
- Check system alerts

### 2. User Management

#### User Search & Filter
```
Filters available:
- Subscription tier (Free/Pro/Premium)
- Registration date range
- Last activity
- Account status (Active/Suspended/Deleted)
- Email verification status
```

#### User Actions
- **View Profile**: Complete user details and activity history
- **Edit Subscription**: Manually adjust tier, apply credits
- **Send Email**: Direct communication via platform
- **Reset Password**: Force password reset
- **Suspend Account**: Temporary restriction with reason
- **Delete Account**: Permanent removal (requires confirmation)

#### Bulk Operations
- Export user lists to CSV
- Send mass emails (with templates)
- Apply promotional credits
- Migrate subscription tiers

### 3. Subscription Management

#### Subscription Overview
- Total subscribers by tier
- Revenue metrics and trends
- Conversion funnel analysis
- Cancellation reasons report

#### Payment Management
- **Failed Payments Queue**: Review and retry failed charges
- **Refund Processing**: Issue full or partial refunds
- **Promotional Codes**: Create and manage discount codes
- **Invoice Management**: View, edit, and resend invoices

#### Dunning Management
- Configure retry schedules
- Customize dunning emails
- View at-risk accounts
- Recovery success rates

### 4. Content Management

#### Prospect Data
- Add/Edit/Delete prospect profiles
- Update statistics and metrics
- Manage prospect images
- Bulk import from CSV

#### Rankings Management
- Adjust ranking algorithms
- Override automatic rankings
- Schedule ranking updates
- Preview before publishing

#### ML Model Management
- View model performance metrics
- Trigger retraining
- A/B test new models
- Rollback to previous versions

### 5. Support Center

#### Ticket Management
- **Queue View**: Unassigned, assigned, resolved
- **Priority Levels**: Critical, High, Normal, Low
- **SLA Tracking**: Response time compliance
- **Escalation Rules**: Automatic routing

#### Ticket Actions
- Assign to team member
- Change priority/category
- Add internal notes
- Use response templates
- Escalate to senior support

#### Knowledge Base
- Create/edit FAQ articles
- Manage categories
- Track article helpfulness
- Identify content gaps

### 6. Analytics & Reporting

#### User Analytics
- User acquisition sources
- Engagement metrics
- Feature usage statistics
- Retention cohorts

#### Revenue Analytics
- MRR growth
- Customer lifetime value (CLV)
- Churn analysis
- Payment method breakdown

#### Custom Reports
- Query builder interface
- Scheduled report delivery
- Export to various formats
- Share with stakeholders

## Common Administrative Tasks

### Processing Refunds
1. Navigate to Subscription Management > Refunds
2. Search for user by email or transaction ID
3. Select refund amount (full or partial)
4. Add refund reason for records
5. Confirm and process
6. System automatically updates Stripe and user account

### Handling Account Issues

#### Locked Account
1. Search for user in User Management
2. Check lock reason (failed logins, suspicious activity)
3. Verify user identity if needed
4. Click "Unlock Account"
5. Send password reset email if appropriate

#### Subscription Disputes
1. Review user's subscription history
2. Check payment records in Stripe dashboard
3. Verify any promotional codes applied
4. Make necessary adjustments
5. Document resolution in user notes

### Data Refresh Procedures

#### Manual Prospect Update
1. Go to Content Management > Prospects
2. Select prospect or bulk select
3. Click "Refresh Data"
4. Choose data source (MLB API, manual)
5. Review changes before applying
6. Publish updates

#### Emergency Data Rollback
1. Access Content Management > Version History
2. Select date/time to rollback to
3. Preview affected records
4. Confirm rollback action
5. Notify users if significant changes

## Monitoring & Alerts

### System Health Monitoring
- **API Response Times**: Target < 200ms p50, < 500ms p95
- **Database Performance**: Query time, connection pool
- **Cache Hit Rates**: Redis performance metrics
- **Error Rates**: 4xx and 5xx responses

### Alert Configuration
```yaml
Critical Alerts (Immediate):
- System downtime
- Payment processing failures
- Security breaches
- Database connection issues

High Priority (Within 1 hour):
- High error rates (>5%)
- Performance degradation
- Failed data refreshes
- Mass user complaints

Standard (Within 4 hours):
- Individual payment failures
- Moderation queue backlog
- Unusual user behavior patterns
```

## Security Procedures

### Incident Response
1. **Detection**: Alert received or issue reported
2. **Assessment**: Determine severity and scope
3. **Containment**: Isolate affected systems
4. **Resolution**: Fix issue and restore service
5. **Documentation**: Complete incident report
6. **Review**: Post-mortem and prevention planning

### Access Control
- All admin actions are logged
- Regular access reviews (monthly)
- Immediate revocation upon role change
- IP allowlisting for admin access
- Required 2FA for all admin accounts

## Best Practices

### Customer Support
1. Always verify user identity before account changes
2. Document all interactions in ticket system
3. Escalate billing issues to finance team
4. Use templates for consistent responses
5. Follow up on critical issues

### Data Management
1. Always backup before bulk operations
2. Test changes in staging first
3. Schedule major updates during low-traffic hours
4. Communicate planned maintenance
5. Monitor post-update metrics

### Compliance
1. Never share user data without consent
2. Follow GDPR guidelines for EU users
3. Process deletion requests within 30 days
4. Maintain audit logs for 90 days minimum
5. Regular security training updates

## Troubleshooting Guide

### Common Issues & Solutions

#### High System Load
1. Check current active users
2. Review recent deployments
3. Examine database query performance
4. Scale resources if needed
5. Enable rate limiting if absent

#### Payment Processing Errors
1. Verify Stripe API status
2. Check webhook configuration
3. Review error logs
4. Test with Stripe test mode
5. Contact Stripe support if needed

#### Data Sync Failures
1. Check external API status
2. Verify API credentials
3. Review rate limits
4. Examine error logs
5. Run manual sync if needed

## Escalation Procedures

### Level 1: Support Admin
- Basic user issues
- Password resets
- Subscription questions
- General troubleshooting

### Level 2: Senior Admin
- Payment disputes
- Account security issues
- Complex technical problems
- Policy exceptions

### Level 3: Engineering Team
- System failures
- Database issues
- Integration problems
- Security incidents

### Level 4: Executive Team
- Legal issues
- Major incidents
- PR situations
- Strategic decisions

## Resources

### Internal Tools
- Admin Dashboard: `[prod-url]/admin`
- Stripe Dashboard: `dashboard.stripe.com`
- Monitoring: Grafana dashboard
- Logs: CloudWatch/ELK Stack

### Documentation
- API Documentation: `/api/docs`
- Database Schema: `docs/database-schema.md`
- Runbooks: `docs/runbooks/`
- Security Policies: `docs/security/`

### Contacts
- Engineering On-Call: [phone/Slack]
- Legal Team: legal@afinewinedynasty.com
- Executive Team: [contact list]
- Third-party Support: [vendor contacts]

---

*Last updated: October 2024*
*Version: 1.0*