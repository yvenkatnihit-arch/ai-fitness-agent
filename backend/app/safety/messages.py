"""Fixed replies for blocked messages (Step 7.6a, D-078). Written by us, never by a model.

The helpline number (Tele-MANAS 14416) is on Venkat's "verify before shipping" list (PROGRESS.md).
"""

CRISIS = (
    "I'm really sorry you are feeling this way. You deserve real support right now, and I am not the right help for this. "
    "Please talk to someone you trust today. In India you can call Tele-MANAS on 14416 (free, any time), and if you might be in "
    "immediate danger, please call 112 or go to the nearest hospital. I'm here for your fitness whenever you are ready."
)
EATING_DISORDER = (
    "I can't help with that, because it could really harm your body. If food, eating or your weight feels hard right now, "
    "please talk to a doctor, a counsellor or someone you trust; Tele-MANAS (14416) is free and open any time. "
    "If you like, I can help you plan balanced, regular meals without counting numbers."
)
EXTREME_DIET = (
    "I can't suggest that, because it is below the safe limits I follow (very low calories, long fasts and very fast weight loss "
    "can harm your health and usually backfire). What I can do is work out a calorie target that is safe for you from your own "
    "details and set a steady pace. Would you like that?"
)
MEDICAL = (
    "I can't give medical advice, diagnose conditions, or advise on medicines, hormones or supplements. Please ask a doctor "
    "about that. I'm happy to help with food, workouts and your plan."
)
RED_FLAG_PAIN = (
    "Please stop the movement that causes this, and see a doctor or physiotherapist before you train that area again. "
    "Sharp pain, swelling, numbness, dizziness or chest pain should be checked by a professional. "
    "I can plan around the problem once you have been seen."
)
# Found by the accuracy audit: "I feel dizzy when I fast" got the exercise-pain wording ("before you train that area again"). Dizziness, fainting
# and chest symptoms are not about a body area, so they get their own wording (same safety category, same rule: a person, not the coach, decides).
RED_FLAG_SYMPTOMS = (
    "Feeling dizzy, faint or having chest pain is worth taking seriously. Please stop what you are doing, sit down, and have something to eat and drink. "
    "If it happens again, or you have chest pain or trouble breathing, please see a doctor. I can't give medical advice, "
    "but I'm happy to help with food and training once you have been checked."
)
INJECTION = "I can only help as your fitness coach, and I can't change my rules or share my instructions. What would you like to know about food or training?"
UNSAFE_OUTPUT = "I'm sorry, I can't give a safe answer to that one. Please ask a doctor for that part, or ask me about food or training."
