# 1. User Journey Flows

## 1.1 Primary User Personas

**Primary Persona: Competitive Dynasty Player**
- Profile: Experienced fantasy baseball player (3+ years dynasty experience)
- Current workflow: Spends 3-8 hours weekly manually researching prospects across multiple platforms
- Pain points: Data fragmentation, analysis paralysis, time constraints
- Goals: Identify undervalued prospects, make informed trade/draft decisions, maintain competitive advantage

**Secondary Persona: Casual Dynasty Player**
- Profile: Newer to dynasty format (1-2 years experience)
- Current workflow: Relies on basic rankings and limited research
- Pain points: Information overwhelm, lack of context for prospect evaluation
- Goals: Learn prospect evaluation, make better decisions without extensive time investment

## 1.2 Core User Journey Flows

### Flow 1: New User Registration & Onboarding
```
Entry Point: Landing page or marketing content
↓
Registration Options:
├── Email/Password Registration
│   ├── Email validation
│   ├── Password creation
│   └── Account verification
└── Google OAuth Sign-in
    ├── Google authentication
    └── Profile linking option
↓
Onboarding Sequence:
├── Welcome & Platform Overview
├── Feature Tour (Rankings, Profiles, Comparisons)
├── Subscription Tier Selection
│   ├── Continue with Free (Top 100 prospects)
│   └── Upgrade to Premium ($9.99/month)
└── Optional: Fantrax Integration Setup
↓
Landing: Prospect Rankings Dashboard (filtered to user's tier)
```

**Key Decision Points:**
- Subscription tier selection (immediate or defer)
- Fantrax integration (immediate or skip)
- Onboarding depth (quick tour vs detailed walkthrough)

### Flow 2: Daily Research Session (Primary Use Case)
```
Entry Point: Direct navigation to dashboard or bookmark
↓
Prospect Rankings Dashboard:
├── Quick scan of top prospects
├── Apply filters based on current needs:
│   ├── Position requirements
│   ├── ETA timeline
│   └── Organization preferences
├── Sort by relevant metrics
└── Identify prospects of interest
↓
Prospect Evaluation:
├── Individual Prospect Profile Review
│   ├── Statistical analysis
│   ├── ML prediction assessment
│   ├── AI-generated outlook review
│   └── Historical comparisons
├── Prospect Comparison (2-4 players)
│   ├── Side-by-side metric comparison
│   ├── ML confidence comparison
│   └── Timeline alignment assessment
└── Decision Documentation
    ├── Add to watchlist
    ├── Export comparison data
    └── Share insights with league mates
↓
Exit: Return to dashboard or close session
```

**Time Target:** Complete evaluation cycle in under 15 minutes for 3-5 prospects

### Flow 3: Trade/Draft Decision Support
```
Entry Point: Specific prospect research need (trade offer, draft upcoming)
↓
Advanced Search & Discovery:
├── Criteria-based search
│   ├── Position + timeline requirements
│   ├── Statistical thresholds
│   └── Organization/league preferences
├── Breakout candidate identification
└── Sleeper prospect discovery
↓
Detailed Analysis:
├── Multi-prospect comparison
├── Team needs assessment (if Fantrax integrated)
├── Trade value analysis
└── Risk/reward evaluation
↓
Decision Support:
├── AI explanation review
├── Historical analog research
├── Dynasty context consideration
└── Final recommendation
↓
Action: Trade execution or draft selection (external)
```

### Flow 4: Mobile Quick-Reference
```
Entry Point: Mobile app during draft/trade discussion
↓
Quick Access:
├── Recently viewed prospects
├── Watchlist access
├── Quick search by name
└── Position-specific rankings
↓
Rapid Assessment:
├── Prospect quick-view cards
├── Swipe navigation between prospects
├── Key metric highlights
└── ML prediction at-a-glance
↓
Comparison (if needed):
├── 2-prospect mobile comparison
├── Key differentiators highlighted
└── Quick decision support
↓
Exit: Return to draft/trade platform
```

**Time Target:** Complete mobile reference check in under 2 minutes

## 1.3 User Journey Success Metrics

**Primary Success Indicators:**
- Time to first prospect evaluation: <3 minutes from registration
- Weekly research time reduction: From 5+ hours to <1 hour
- User retention: >95% week-1, >80% month-1, >60% month-6
- Feature adoption: 70% use comparison tool within first week

**Behavioral Milestones:**
- Day 1: Complete registration, view top 25 prospects
- Day 3: Use filtering and individual prospect profiles
- Week 1: Complete first prospect comparison
- Week 2: Establish regular research pattern (2-3 sessions)
- Month 1: Consider premium upgrade or integrate Fantrax

---
