# 2. Information Architecture

## 2.1 Site Structure & Navigation Hierarchy

```
A Fine Wine Dynasty
├── Authentication (modal/overlay)
│   ├── Sign In
│   ├── Register
│   └── Password Reset
├── Main Application
│   ├── Prospect Rankings Dashboard (Primary Landing)
│   │   ├── Rankings Table (Top 100/500 based on tier)
│   │   ├── Filter Panel
│   │   ├── Search Bar
│   │   └── Quick Actions
│   ├── Prospect Profiles
│   │   ├── Individual Prospect Pages
│   │   │   ├── Overview Tab
│   │   │   ├── Statistics Tab
│   │   │   ├── Scouting Grades Tab
│   │   │   ├── ML Prediction Tab
│   │   │   └── Comparisons Tab
│   │   └── Prospect Comparison Tool
│   │       ├── Multi-prospect Selection
│   │       ├── Side-by-side Analysis
│   │       └── Export/Share Options
│   ├── Advanced Tools (Premium)
│   │   ├── Advanced Search & Discovery
│   │   ├── Breakout Candidate Identification
│   │   ├── Historical Data Analysis
│   │   └── Custom Report Builder
│   ├── User Account
│   │   ├── Profile Management
│   │   ├── Subscription Management
│   │   ├── Fantrax Integration
│   │   ├── Watchlist
│   │   └── Saved Searches
│   └── Support & Resources
│       ├── Help Documentation
│       ├── Feature Tutorials
│       ├── Contact Support
│       └── Feedback System
```

## 2.2 Navigation Design Patterns

**Primary Navigation (Desktop):**
- Horizontal top navigation bar with main sections
- Logo/brand (left) → Dashboard | Prospects | Tools | Account (center) → Upgrade/Profile (right)
- Persistent across all screens except authentication flows

**Secondary Navigation:**
- Contextual sub-navigation within sections (tabs, sidebars)
- Breadcrumb navigation for deep sections (Prospects > Individual > Comparisons)
- Quick actions toolbar for frequently used functions

**Mobile Navigation:**
- Collapsible hamburger menu with primary sections
- Bottom navigation bar for core functions (Dashboard, Search, Watchlist, Profile)
- Swipe gestures for prospect navigation

## 2.3 Content Organization Strategy

**Information Density Approach:**
- **Level 1 (Dashboard):** High-density overview with essential metrics
- **Level 2 (Profiles):** Medium-density detailed view with progressive disclosure
- **Level 3 (Analysis):** Low-density focused view for deep analysis

**Content Prioritization (Mobile-First):**
1. **Critical:** ML prediction, prospect name, position, ETA
2. **Important:** Key statistics, scouting grades, organization
3. **Supplementary:** Historical data, detailed analysis, comparisons
4. **Premium:** Advanced analytics, export options, unlimited access

**Data Hierarchy:**
- Prospects organized by ML-powered dynasty ranking (primary sort)
- Secondary sorts: Position, ETA, Age, Organization, Recent performance
- Filter categories: Position, League Level, Age Range, ETA, Organization, Region

---
