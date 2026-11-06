// Choices shown in onboarding, with friendly labels. The VALUES must match the backend
// exactly (backend/app/core/vocabulary.py and app/calc/targets.py); options.test.ts checks this.

export const SEXES = [
  ['female', 'Female'],
  ['male', 'Male'],
  ['other', 'Other / prefer not to say'],
] as const

// Same levels and wording as backend/app/calc/tdee.py (D-020).
export const ACTIVITY_LEVELS = [
  ['sedentary', 'Mostly sitting', 'Desk job, little or no exercise'],
  ['light', 'Lightly active', 'Exercise 1–3 days a week'],
  ['moderate', 'Moderately active', 'Exercise 3–5 days a week'],
  ['active', 'Very active', 'Exercise 6–7 days a week'],
  ['very_active', 'Extremely active', 'Hard daily training or a physical job'],
] as const

export const GOALS = [
  ['fat_loss', 'Lose fat', 'Eat a little less than you burn, keep your muscle.'],
  ['muscle_gain', 'Build muscle', 'Eat a little more than you burn, and train for strength.'],
  ['recomp', 'Lose fat and build muscle', 'A small deficit with plenty of protein. Slower, steady change.'],
  ['weight_gain', 'Gain weight', 'For people who want to put on weight overall.'],
  ['general_fitness', 'Get fitter and stronger', 'Eat to maintain your weight; the training does the work.'],
] as const

// Same values as backend/app/core/vocabulary.py (Pace). Pace only picks a point inside the safety limits (D-042).
export const PACES = [
  ['slow', 'Slow and steady', 'Gentler changes that are easiest to keep up.'],
  ['normal', 'Normal', 'A balanced pace. A good choice for most people.'],
  ['fast', 'Fast and intense', 'The quickest pace that is still safe. It takes more discipline.'],
] as const

// Only cuisines that have validated food data (backend Cuisine). More are added after their data is loaded.
export const CUISINES = [
  ['indian', 'Indian', 'Rotis, dals, sabzis, rice dishes, South Indian breakfasts and more'],
] as const

export const DIETS = [
  ['vegetarian', 'Vegetarian', 'Includes dairy, no eggs, meat or fish'],
  ['eggetarian', 'Eggetarian', 'Vegetarian plus eggs'],
  ['non_vegetarian', 'Non-vegetarian', 'Includes eggs, meat and fish'],
  ['vegan', 'Vegan', 'No animal products, including dairy'],
] as const

export const EXPERIENCE = [
  ['beginner', 'Beginner', "New to training, or back after a long break"],
  ['intermediate', 'Intermediate', 'Training regularly for 6 months or more'],
  ['advanced', 'Advanced', 'Several years of consistent training'],
] as const

export const LOCATIONS = [
  ['gym', 'Gym'],
  ['home', 'Home'],
  ['both', 'Both'],
] as const

export const EQUIPMENT = [
  ['dumbbells', 'Dumbbells'],
  ['barbell', 'Barbell'],
  ['kettlebell', 'Kettlebell'],
  ['resistance_bands', 'Resistance bands'],
  ['pull_up_bar', 'Pull-up bar'],
  ['bench', 'Bench'],
  ['cable_machine', 'Cable machine'],
  ['leg_press_machine', 'Leg press machine'],
  ['smith_machine', 'Smith machine'],
  ['treadmill', 'Treadmill'],
  ['stationary_bike', 'Exercise bike'],
  ['jump_rope', 'Skipping rope'],
  ['yoga_mat', 'Yoga mat'],
] as const

export const INJURY_AREAS = [
  ['shoulder', 'Shoulder'],
  ['knee', 'Knee'],
  ['lower_back', 'Lower back'],
  ['neck', 'Neck'],
  ['wrist', 'Wrist'],
  ['elbow', 'Elbow'],
  ['hip', 'Hip'],
  ['ankle', 'Ankle'],
] as const

// Same names as SCREENING_FLAGS in backend/app/safety/safety_config.py.
export const SCREENING_QUESTIONS = [
  ['pregnant_or_breastfeeding', 'Are you pregnant or breastfeeding?'],
  ['diabetes', 'Do you have diabetes?'],
  ['heart_or_bp', 'Do you have a heart condition or high blood pressure?'],
  ['kidney', 'Do you have kidney disease?'],
  ['recent_surgery_or_injury', 'Have you had surgery or a serious injury in the last 6 months?'],
  ['eating_disorder_history', 'Have you ever been diagnosed with, or treated for, an eating disorder?'],
] as const

export const MAX_DISLIKED_FOODS = 30
