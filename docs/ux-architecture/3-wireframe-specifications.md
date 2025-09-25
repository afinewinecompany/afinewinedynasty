# 3. Wireframe Specifications

## 3.1 Prospect Rankings Dashboard (Primary Screen)

**Desktop Layout (1440px+):**
```
┌─────────────────────────────────────────────────────────────────┐
│ [Logo] Dashboard | Prospects | Tools     [Search] [Profile] [⚡] │ Header (64px)
├─────────────────────────────────────────────────────────────────┤
│ 🔍 Search Prospects    [Filters ▼] [Export] [⚙️]    Updated 2h  │ Action Bar (48px)
├─────────────────────────────────────────────────────────────────┤
│ ┌─ Filters (240px) ─┐ ┌─── Main Rankings Table (remainder) ─────┐│
│ │ Position          │ │ Rank | Name | Pos | Org | Age | ETA | ML│ │
│ │ ☑️ All Positions   │ │  1   | Elijah Green | OF | WSH | 19 |2025│●│ │ Row (48px)
│ │ ☑️ C □ 1B □ 2B     │ │  2   | Termarr Johnson |2B| PIT| 18 |2026│●│ │ each
│ │                   │ │  3   | Travis Bazzana |2B| CLE | 21 |2025│●│ │
│ │ Organization      │ │  4   | Jac Caglianone |1B| KC  | 21 |2025│○│ │
│ │ [All Teams ▼]     │ │  5   | Charlie Condon |3B| COL | 21 |2025│○│ │
│ │                   │ │ ...  | [25 more rows visible]        │ │ │
│ │ ETA               │ │                                        │ │ │
│ │ 2024 ████░░░░      │ │ [Load More] [Page 2] [50 per page ▼] │ │ │
│ │ 2025 ██████░░░     │ │                                        │ │ │
│ │ 2026+ ████░░░░     │ └────────────────────────────────────────┘ │
│ │                   │                                            │
│ │ Age Range         │                                            │
│ │ 17 ●──────●──● 24 │                                            │
│ │                   │                                            │
│ │ [Clear Filters]   │                                            │
│ └───────────────────┘                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Key Interactive Elements:**
- **ML Prediction Indicators:** Color-coded dots (Green=High, Yellow=Medium, Red=Low confidence)
- **Sortable Columns:** Click headers to sort, visual indicators for sort direction
- **Row Hover Actions:** Quick-view preview, add to watchlist, compare button
- **Filter Panel:** Collapsible on mobile, always visible on desktop
- **Search:** Auto-complete with fuzzy matching, recent searches

**Responsive Behavior:**
- **Tablet (768-1024px):** Filter panel collapses to dropdown, reduced columns
- **Mobile (320-767px):** Card-based layout, bottom sheet filters, horizontal scroll for table

## 3.2 Individual Prospect Profile Page

**Layout Structure:**
```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Rankings                              [+ Watchlist] [⚡]│ Nav (48px)
├─────────────────────────────────────────────────────────────────┤
│ ┌─ Prospect Header (360px) ─┐ ┌─── ML Prediction Card ─────────┐ │
│ │ [Photo] Elijah Green      │ │ MLB Success Probability         │ │ Header (120px)
│ │         OF | Washington   │ │ ████████░░ 87% HIGH CONFIDENCE  │ │
│ │         Age 19 | ETA 2025 │ │ "Elite power potential with     │ │
│ │                           │ │ developing plate discipline..." │ │
│ └───────────────────────────┘ └─────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ [Overview] [Statistics] [Scouting] [Comparisons] [History]      │ Tab Nav (40px)
├─────────────────────────────────────────────────────────────────┤
│ ┌─ Current Season Stats ────────────────────────────────────────┐ │
│ │ Level: AAA Norfolk | 67 Games | .287/.354/.521 | 15 HR      │ │ Content Area
│ │ ┌─ Key Metrics ─┐ ┌─ Scouting Grades ─┐ ┌─ Recent Form ────┐│ │ (variable)
│ │ │ wOBA: .389     │ │ Hit: 60/55 Power: 70│ │ Last 30 days:    ││ │
│ │ │ wRC+: 156      │ │ Run: 40/45 Field: 55│ │ .312/.403/.625   ││ │
│ │ │ K%: 23.1%      │ │ Arm: 60/55         │ │ 6 HR, 18 RBI    ││ │
│ │ └───────────────┘ └─────────────────────┘ └──────────────────┘│ │
│ │                                                                │ │
│ │ ┌─ Performance Trend Chart ─────────────────────────────────┐  │ │
│ │ │ [Interactive chart showing monthly performance trends]     │  │ │
│ │ └────────────────────────────────────────────────────────────┘  │ │
│ └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Tab-Specific Content:**

**Overview Tab:**
- Current season performance summary
- Key developmental milestones
- Recent news and updates
- Dynasty timeline projection

**Statistics Tab:**
- Multi-year statistical progression
- Advanced metrics and ratios
- Level-by-level performance breakdown
- Comparative performance vs league averages

**Scouting Tab:**
- Comprehensive scouting grades from multiple sources
- Grade progression over time
- Video highlights integration (future phase)
- Scouting report excerpts

**Comparisons Tab:**
- Historical player comparisons
- Current prospect comparisons
- Organizational depth chart context
- Trade value analysis

## 3.3 Prospect Comparison Tool

**Side-by-Side Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ Compare Prospects                               [Export] [Share] │ Header
├─────────────────────────────────────────────────────────────────┤
│ [+ Add Prospect] [Elijah Green] [Travis Bazzana] [Empty Slot]   │ Prospect Selector
├─────────────────────────────────────────────────────────────────┤
│ ┌───────────────┬───────────────┬───────────────┬─────────────┐ │
│ │ Metric        │ Elijah Green  │ Travis Bazzana│ Difference  │ │
│ ├───────────────┼───────────────┼───────────────┼─────────────┤ │
│ │ ML Prediction │ 87% (High)    │ 72% (Medium)  │ +15% ✓      │ │
│ │ Age           │ 19            │ 18            │ +1 year     │ │
│ │ ETA           │ 2025          │ 2026          │ 1 yr earlier│ │
│ │ Position      │ OF            │ 2B            │ Different   │ │
│ │ Current Level │ AAA           │ AA            │ +1 level ✓  │ │
│ │ Hit Grade     │ 60/55         │ 65/60         │ -5 points   │ │
│ │ Power Grade   │ 70/65         │ 50/50         │ +20 pts ✓   │ │
│ │ wOBA (2024)   │ .389          │ .378          │ +.011 ✓     │ │
│ └───────────────┴───────────────┴───────────────┴─────────────┘ │
│                                                                 │
│ ┌─ Scouting Radar Comparison ────────────────────────────────┐  │
│ │ [Interactive radar chart comparing all tool grades]        │  │
│ └────────────────────────────────────────────────────────────┘  │
│                                                                 │
│ ┌─ AI Analysis Summary ──────────────────────────────────────┐  │
│ │ "Green offers superior power potential and earlier ETA,    │  │
│ │ while Bazzana provides better hit tool and positional      │  │
│ │ versatility. For dynasty leagues prioritizing immediate    │  │
│ │ impact, Green edges ahead. For long-term floor..."        │  │
│ └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Interactive Elements:**
- **Drag-and-drop prospect selection:** Easy addition/removal of prospects
- **Metric highlighting:** Visual indicators for advantages (✓, colors)
- **Expandable sections:** Detailed breakdowns on click
- **Export options:** PDF, CSV, or shareable link generation

## 3.4 Mobile Wireframes

**Mobile Dashboard (375px):**
```
┌─────────────────────────────┐
│ ☰ A Fine Wine Dynasty   👤  │ Header (56px)
├─────────────────────────────┤
│ 🔍 Search prospects...      │ Search (44px)
├─────────────────────────────┤
│ [All] [OF] [SS] [SP] [More] │ Quick Filters (40px)
├─────────────────────────────┤
│ ┌─ Prospect Card 1 ───────┐ │ Card Stack
│ │ 1. Elijah Green     ● H │ │ (120px each)
│ │    OF | WSH | Age 19    │ │
│ │    87% ML | ETA 2025    │ │
│ │    .287/.354/.521 AAA   │ │
│ │    [View] [Compare] [+] │ │
│ └─────────────────────────┘ │
│                             │
│ ┌─ Prospect Card 2 ───────┐ │
│ │ 2. Travis Bazzana   ● M │ │
│ │    2B | CLE | Age 18    │ │
│ │    72% ML | ETA 2026    │ │
│ │    .378/.462/.589 AA    │ │
│ │    [View] [Compare] [+] │ │
│ └─────────────────────────┘ │
│                             │
│ [Load More Prospects]       │
├─────────────────────────────┤
│ [🏠] [🔍] [⭐] [⚙️] [👤]   │ Bottom Nav (60px)
└─────────────────────────────┘
```

**Mobile Prospect Profile:**
```
┌─────────────────────────────┐
│ ← Elijah Green      [⭐] [↗]│ Header
├─────────────────────────────┤
│ ┌─ Photo ─┐ OF | Washington │ Profile Header
│ │ [Image] │ Age 19 | 2025   │ (100px)
│ │         │ 87% High Conf   │
│ └─────────┘                 │
├─────────────────────────────┤
│ ● Overview  ○ Stats  ○ More │ Tab Navigation
├─────────────────────────────┤
│ Current Performance         │ Content
│ AAA Norfolk | 67 Games     │ (scrollable)
│                             │
│ .287/.354/.521 | 15 HR      │
│                             │
│ ┌─ Key Stats ─────────────┐ │
│ │ wOBA: .389              │ │
│ │ wRC+: 156               │ │
│ │ K%: 23.1%               │ │
│ └─────────────────────────┘ │
│                             │
│ Recent Form (Last 30 days)  │
│ .312/.403/.625 | 6 HR       │
│                             │
│ AI Outlook                  │
│ "Elite power potential with │
│ developing plate discipline │
│ gives Green excellent..."   │
│ [Read More]                 │
│                             │
│ ┌─────────────────────────┐ │
│ │ [Compare with Others]   │ │
│ │ [Add to Watchlist]     │ │
│ │ [Share Profile]        │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘
```

---
