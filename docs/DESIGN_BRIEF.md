# Design brief — frontend redesign (D-058)

Venkat's design prompt is saved word for word in **Part 2**. **Part 1** is the analysis: what we will use, what clashes with the project's fixed rules (and needs Venkat's decision), and what needs backend data that doesn't exist yet. Per D-058, the redesign starts only after the backend is finished, and only the frontend/visual parts of the prompt are used.

## Part 1 — Analysis (2026-11-07)

### A. Use as written (pure visual design, no conflict)
- **Identity:** dark cinematic, neon lime accent (#B7FF35 / #8EDB28), the full colour list in section 1, glass cards, subtle glow, rounded cards. Becomes our token set in `index.css`; the WCAG contrast test (`theme.test.ts`) keeps checking it. Lime is a light colour, so text ON lime buttons must be the dark background colour, not white.
- **Dashboard** layout: greeting, date, big animated calorie ring, macro cards (protein most prominent), insight card.
- **AI Coach screen:** chat bubbles, typing/loading animation, suggested prompt cards, quick actions (built together with the Phase 7 chat).
- **Nutrition:** meal sections (breakfast, lunch, evening snack, dinner; our data also has mid-morning), search, add food, macro rings and bars, expandable sections.
- **Workouts:** today's workout, weekly schedule, split, set-completion buttons, weight/rep inputs, rest countdown, completion screen, PR celebration (the logging parts arrive with Phase 8 logging).
- **Progress:** dark charts with lime highlights, tooltips, weekly/monthly views (Phase 8/9 stats data).
- **Profile & settings** cards (built with the Profile step).
- **Navigation:** desktop sidebar (Dashboard, AI Coach, Nutrition, Workouts, Progress, Profile) and mobile bottom bar.
- **Landing, sign-in and sign-up** screens.
- **Motion:** page transitions, staggered cards, counting numbers, animated rings/bars, celebrations; always honouring `prefers-reduced-motion`.
- **Type and icons:** a modern sans (Inter / Manrope / Space Grotesk), Lucide icons only.
- **Mobile-first**, every state designed (loading, empty, success, error).
- **Libraries:** Framer Motion (now published as `motion`), `lucide-react`, `recharts`; shadcn/ui only for pieces we actually need (it copies components into the repo). Each new package goes through the 2-week age rule (D-030).

### B. Clashes with fixed project rules (Venkat decides before the redesign)
1. **Exercise images / demonstrations / anatomical illustrations** (sections 5, 8). CLAUDE.md fixed decision: *no exercise videos or images; text instructions with form cues.* Proposal: keep text cues; use simple Lucide/abstract muscle-group icons, not anatomy drawings or photos.
2. **Food images / thumbnails and "high-quality fitness imagery"** (sections 1, 4, 10). We have no licensed image set; food logging is text only. Proposal: category icons and colour chips for foods; one or two licensed (or self-made) abstract hero visuals for the landing page only.
3. **Exercise library inside Workouts** (section 5). Removed on Venkat's request (D-056). Proposal: leave it out; "swap this exercise" can show alternatives inline later.
4. **Microphone / voice UI** (section 3). Text-only, English-only MVP, and "no mock data/placeholders in real workflows": a mic button that does nothing would be a fake control. Proposal: no mic until voice is a real feature.
5. **Dark only vs. our light + dark (D-044, "Fresh & energetic").** The prompt is dark-only and replaces the green + orange palette. Proposal: dark becomes the main look; decide whether to keep a light mode.
6. **"AI-generated daily insights"** (section 2F). The cost rule says never call the LLM for what code can do. Lines like "you need another 35 g of protein" are arithmetic. Proposal: insights are code rules over today's numbers (free, instant, always correct); the card is styled as "AI" but no model call.
7. **Fonts.** Inter/Manrope/Space Grotesk replace Bricolage Grotesque + Source Sans 3. Proposal: self-host them (`@fontsource`) so visitors' IPs don't go to Google (open item from D-044).

### C. Needs data the backend doesn't have yet (show only when it is real)
"No mock data in real workflows" means these widgets appear only once their data exists:
| Widget | Needs | Where it would come from |
|---|---|---|
| Calories burned, workout duration, streak, weekly consistency, completion | workout logs + a code estimate of burn | Phase 8 workout logging (+ a MET-based calculation in code) |
| Water tracker | a water log table + target rule | not in the brief yet: new feature, needs Venkat's yes |
| Body composition | body-fat entries | not in the brief yet: new feature |
| Personal records, strength progression | workout set logs | Phase 8 |
| Notifications bell | the reminders/nudges feature (D-047) | Phase 7+ |
| Calorie / protein history, weight trend | meal logs (exist), weight entries (exist) | stats endpoints, Phase 8 |
| Muscle group selection | the focus-areas step | 6.6g (next backend step) |

### D. Mapping to our roadmap
The prompt's order (design system → components → dashboard → coach → nutrition → workouts → progress → profile → landing/auth → motion → responsive → polish) fits as the **F phase** after the backend. Each item becomes one small step with its own tests, as usual. The coach, logging and stats screens can only be redesigned after their backend exists, which is why D-058 puts the redesign at the end.

---

## Part 2 — Venkat's prompt (verbatim)

MASTER PROMPT: DESIGN A PREMIUM AI FITNESS AGENT APPLICATION

PROJECT VISION

I am developing a premium AI-powered Fitness Agent application that combines personal fitness coaching, diet tracking, nutrition management, workout planning, and fitness analytics.

I want you to transform the frontend into an exceptionally attractive, modern, premium application.

My preferred visual direction is:

DARK CINEMATIC + NEON LIME + FUTURISTIC FITNESS AESTHETICS.

The application should look like a professionally designed fitness startup product that users genuinely enjoy opening every day.

Take visual inspiration from:

- Apple Fitness+
- Whoop
- Nike Training Club
- Premium fitness analytics dashboards.
- Modern futuristic AI applications.

Do not create a generic dashboard. I want a distinctive visual identity, beautiful layouts, sophisticated animations, and exceptional attention to detail.

1. DESIGN SYSTEM AND COLOR PALETTE

Establish a consistent design system throughout the application.

Primary colors

- Main background: #080A09
- Secondary background: #101411
- Card background: #141916
- Elevated surfaces: #1B211D
- Primary accent: #B7FF35
- Secondary accent: #8EDB28
- Primary text: #F5F7F4
- Secondary text: #929C94
- Border color: rgba(255,255,255,0.08)

Design characteristics

- Deep cinematic black backgrounds.
- Neon lime green highlights.
- Sophisticated dark gradients.
- Subtle glowing effects.
- Premium glassmorphism.
- Smooth rounded cards.
- Minimalist icons.
- Modern typography.
- Beautiful spacing and alignment.
- High-quality fitness imagery.

Use neon green strategically for important metrics, active navigation, buttons, progress indicators, and interactive elements.

Avoid excessive colors. Maintain a premium and consistent appearance.

2. DASHBOARD – THE MOST IMPORTANT SCREEN

The dashboard must create an impressive first impression.

When users open the application, they should immediately see their daily fitness performance.

Dashboard layout

A. Welcome section

- Personalized greeting.
- User profile avatar.
- Current date.
- Motivational fitness message.
- Notification icon.

B. Daily calorie tracker

Create a large, beautiful circular calorie progress indicator.

Display:

- Daily calorie target.
- Calories consumed.
- Calories remaining.
- Calories burned.

Use an animated circular ring with a subtle neon lime glow.

Make this one of the dashboard's main visual highlights.

C. Macronutrient tracking

Create three beautiful interactive cards:

- Protein.
- Carbohydrates.
- Fats.

Each card should display:

- Daily target.
- Consumed amount.
- Remaining amount.
- Animated progress bar.

Give protein a particularly prominent visual treatment.

D. Workout statistics

Display:

- Workout completion.
- Total workout duration.
- Weekly training consistency.
- Calories burned.
- Current streak.

Use attractive statistic cards with subtle animations.

E. Water intake

Create an interactive water tracker with:

- Daily water target.
- Current consumption.
- Animated water progress.
- Quick-add buttons.

F. AI-generated daily insights

Create an attractive AI recommendation card with a glowing AI icon.

Examples:

- You need another 35g of protein today.
- Your calorie intake is currently on target.
- Consider increasing your water intake.
- Your upper-body training consistency is improving.

Make these insights visually distinct.

3. AI FITNESS COACH – SIGNATURE FEATURE

This should be one of the most impressive sections of the application.

I want users to feel like they have their own intelligent personal fitness coach.

Interface design

- Premium dark chat interface.
- Beautiful AI assistant avatar.
- Animated response indicators.
- Smooth typing animations.
- Modern chat bubbles.
- Attractive message transitions.
- Suggested question cards.
- Quick-action buttons.
- Clean conversation history.
- Elegant input field.
- Microphone icon for voice interaction UI.

Suggested prompts

Display attractive interactive suggestions:

- Analyze my diet.
- Create today's workout.
- Calculate my protein requirements.
- Help me build muscle.
- Create a fat-loss diet.
- Analyze my fitness progress.

Special visual treatment

Create a distinctive AI assistant experience using:

- Subtle neon glow.
- Animated AI visualizer.
- Smooth message appearance.
- Elegant loading animations.
- Interactive suggestion cards.

The AI coach should feel intelligent, futuristic, and premium.

4. NUTRITION AND DIET TRACKING

Create a visually attractive nutrition management section.

Main features

- Daily calorie consumption.
- Protein tracking.
- Carbohydrate tracking.
- Fat tracking.
- Daily calorie goal.
- Meal-wise food tracking.
- Food search.
- Food nutritional information.
- Add food functionality.

Meal organization

Create individual sections for:

- Breakfast.
- Lunch.
- Evening snacks.
- Dinner.

Each section should have:

- Meal title.
- Food images or thumbnails.
- Food name.
- Calories.
- Protein.
- Carbohydrates.
- Fats.
- Add food button.

Visual effects

- Animated macro progress rings.
- Smooth calorie progress bars.
- Attractive nutrition cards.
- Beautiful food thumbnails.
- Interactive charts.
- Expandable meal sections.
- Smooth transitions.

Make food logging simple, visually satisfying, and intuitive.

5. WORKOUT PLANNER AND TRACKER

The workout section should look like a premium strength-training application.

Workout dashboard

Include:

- Today's workout.
- Weekly workout schedule.
- Workout split.
- Muscle group selection.
- Training history.
- Exercise library.
- Personal records.
- Workout duration.

Exercise cards

Each exercise card should display:

- Exercise image or demonstration.
- Exercise name.
- Target muscle group.
- Sets.
- Repetitions.
- Weight.
- Rest duration.

Workout tracking experience

Create:

- Interactive set completion buttons.
- Weight and repetition input controls.
- Rest countdown timer.
- Animated workout progress.
- Workout completion screen.
- Personal record celebration animation.

Muscle group selection

Create visually attractive muscle group cards for:

- Chest.
- Back.
- Shoulders. 
- Biceps.
- Triceps.
- Legs.
- Abs.
- Traps.

Use attractive anatomical illustrations or muscle group visuals.

Make the entire workout experience feel interactive and motivating.

6. FITNESS PROGRESS AND ANALYTICS

Create a sophisticated fitness analytics dashboard.

Include:

- Body weight progression.
- Body composition tracking.
- Calorie consumption history.
- Protein intake history.
- Workout consistency.
- Strength progression.
- Weekly activity.
- Monthly performance.

Chart design

Use beautiful interactive charts.

Include:

- Line charts.
- Bar charts.
- Progress graphs.
- Weekly comparisons.
- Monthly performance reports.

Use dark chart backgrounds with neon lime highlights.

Charts should have smooth transitions, clean labels, interactive tooltips, and readable legends.

Avoid cluttered data visualizations.

7. PROFILE AND PERSONALIZATION

Create a premium user profile section.

Include:

- Profile picture.
- Name.
- Fitness goal.
- Current weight.
- Target weight.
- Height.
- Fitness experience.
- Preferred training style.
- Dietary preferences.
- Activity level.

Include attractive settings cards and editable profile sections.

8. CINEMATIC FRONTEND ANIMATIONS AND SPECIAL EFFECTS

This is extremely important.

I want the application to feel alive.

Use Framer Motion or an equivalent animation library where appropriate.

Implement the following:

Page animations

- Smooth page transitions.
- Fade-in animations.
- Slide-up animations.
- Staggered card appearances.
- Scroll-triggered animations.

Interactive animations

- Hover effects on cards.
- Smooth button interactions.
- Animated progress rings.
- Number-counting animations.
- Animated progress bars.
- Interactive charts.
- Smooth modal transitions.
- Animated dropdown menus.

Cinematic effects

- Subtle neon green background glow.
- Radial gradient lighting.
- Soft ambient lighting.
- Subtle floating particles in selected sections.
- Glassmorphism cards.
- Gradient borders.
- Beautiful hover lighting effects.

Fitness-specific effects

- Workout completion celebration.
- Animated achievement badges.
- Personal record animations.
- Smooth rest timer transitions.
- Daily goal completion effects.

IMPORTANT: Animations should be smooth and sophisticated, not excessive or distracting.

Maintain excellent performance.

9. PREMIUM NAVIGATION

Desktop

Create an elegant vertical sidebar with:

- Dashboard.
- AI Coach.
- Nutrition.
- Workouts.
- Progress.
- Profile.

Design requirements:

- Dark translucent sidebar.
- Minimalist icons.
- Neon lime active indicator.
- Smooth hover transitions.
- Elegant active navigation state.

Mobile

Create a premium bottom navigation bar.

Ensure:

- Proper touch interactions.
- Clear active states.
- Responsive navigation.
- Smooth transitions.
- No overlapping content.

10. LANDING AND LOGIN EXPERIENCE

Create a visually impressive first-time user experience.

Landing page

Include:

- Strong fitness-focused headline.
- Premium cinematic fitness imagery.
- Neon lime call-to-action buttons.
- Attractive feature sections.
- Animated statistics.
- Beautifully designed application previews.

The landing page should communicate that this is an intelligent AI-powered fitness platform.

Login and signup

Create modern authentication screens with:

- Minimal layouts.
- Dark backgrounds.
- Neon lime buttons.
- Elegant input fields.
- Smooth transitions.
- Beautiful validation states.

11. TYPOGRAPHY AND ICONOGRAPHY

Use modern fonts such as:

- Inter.
- Manrope.
- Space Grotesk.

Use:

- Bold typography for important statistics.
- Large numbers for calorie and macro tracking.
- Clean typography for descriptions.
- Consistent font weights.

Use Lucide icons consistently.

Avoid mixing different icon styles.

12. RESPONSIVE DESIGN

The application must look exceptional on:

- Desktop.
- Laptop.
- Tablet.
- Mobile.

Prioritize mobile-first design.

Requirements:

- Responsive dashboard grid.
- Adaptive cards.
- Responsive charts.
- Proper typography scaling.
- Touch-friendly controls.
- Optimized image sizing.
- Responsive navigation.
- Consistent spacing across screen sizes.

Do not simply shrink the desktop layout to fit mobile. Design an intentional mobile experience.

13. TECHNICAL DESIGN EXPECTATIONS

Use appropriate frontend technologies and libraries compatible with the existing project.

Recommended:

- React.
- Tailwind CSS.
- Framer Motion.
- Lucide React.
- Recharts.
- Shadcn/UI.

Use reusable components and maintain a consistent design system.

Keep the UI clean, modular, responsive, and maintainable.

Do not introduce unnecessary dependencies.

14. QUALITY AND DESIGN STANDARDS

Follow these rules throughout the entire application:

1. Every page must maintain the same dark cinematic identity.
2. Avoid generic AI-generated dashboard layouts.
3. Avoid excessive gradients.
4. Avoid unnecessary animations.
5. Avoid cluttered cards.
6. Avoid inconsistent spacing.
7. Avoid oversized typography without purpose.
8. Use high-quality imagery.
9. Maintain clear visual hierarchy.
10. Make every interactive element feel polished.
11. Ensure loading, empty, success, and error states are beautifully designed.
12. Respect reduced-motion accessibility preferences.

15. IMPLEMENTATION PRIORITIES

Approach the frontend redesign in this order:

1. Establish the complete design system.
2. Create reusable UI components.
3. Design the dashboard.
4. Design the AI Fitness Coach.
5. Design nutrition and diet tracking.
6. Design workout planning and tracking.
7. Design progress analytics.
8. Design profile and personalization.
9. Design landing and authentication screens.
10. Add animations and special effects.
11. Optimize responsive layouts.
12. Polish every interaction and visual detail.

Do not settle for static mockups. Build complete, interactive frontend experiences.

FINAL CREATIVE DIRECTION

I want the finished application to feel like a combination of:

- Apple Fitness+'s visual sophistication.
- Whoop's fitness analytics.
- Nike Training Club's workout experience.
- A futuristic AI-powered personal fitness assistant.

The overall aesthetic must be:

Dark. Cinematic. Athletic. Futuristic. Minimal. Premium.

The dashboard's calorie ring, protein tracker, workout statistics, and AI assistant should be the most visually impressive elements.

Use neon lime as the signature accent color.

The application should feel like a product that users would happily pay for.

Most importantly, pay attention to the smallest details: spacing, shadows, typography, transitions, button states, card layouts, chart styling, and mobile responsiveness.

I want an exceptional frontend experience, not just a functional collection of pages.

Start by examining the existing frontend and then implement this complete visual transformation.
