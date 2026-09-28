"""
questions.py
All 14 questions we ask Jev about every review.
7 topics x 2 questions:
  - "<topic>_mentioned" : Noul  -> is there enough information? (yes/no probability)
  - "<topic>_rating"    : Score -> how satisfied is the reviewer? (5 levels)
"""

from typesafe_sdk import Noul, Score

# Topic name shown to users  ->  short id used in the question keys
TOPICS = {
    "Camera": "camera",
    "Battery": "battery",
    "Display": "display",
    "Design": "design",
    "Performance": "performance",
    "Build Quality": "build_quality",
    "Value for Money": "value_for_money",
}

# The 5 satisfaction levels. Position 0 = 1 star ... position 4 = 5 stars.
SATISFACTION_LEVELS = [
    "Very dissatisfied",                                               # 1 star
    "Dissatisfied",                                                    # 2 stars
    "Neither satisfied nor dissatisfied, or balanced mixed feedback",  # 3 stars
    "Satisfied",                                                       # 4 stars
    "Very satisfied",                                                  # 5 stars
]

QUESTIONS = {
    # Camera
    "camera_mentioned": Noul(
        instructions="Does the reviewer describe an opinion or experience about the camera's photos or videos?"
    ),
    "camera_rating": Score(
        instructions="How satisfied is the reviewer with the camera?",
        criteria=SATISFACTION_LEVELS,
    ),

    # Battery
    "battery_mentioned": Noul(
        instructions="Does the reviewer describe an opinion or experience about battery life or charging?"
    ),
    "battery_rating": Score(
        instructions="How satisfied is the reviewer with the battery experience?",
        criteria=SATISFACTION_LEVELS,
    ),

    # Display
    "display_mentioned": Noul(
        instructions="Does the reviewer describe an opinion or experience about the screen?"
    ),
    "display_rating": Score(
        instructions="How satisfied is the reviewer with the display?",
        criteria=SATISFACTION_LEVELS,
    ),

    # Design
    "design_mentioned": Noul(
        instructions="Does the reviewer describe an opinion or experience about the phone's appearance, shape, or ergonomics?"
    ),
    "design_rating": Score(
        instructions="How satisfied is the reviewer with the design?",
        criteria=SATISFACTION_LEVELS,
    ),

    # Performance
    "performance_mentioned": Noul(
        instructions="Does the reviewer describe an opinion or experience about speed, responsiveness, multitasking, or gaming?"
    ),
    "performance_rating": Score(
        instructions="How satisfied is the reviewer with the performance?",
        criteria=SATISFACTION_LEVELS,
    ),

    # Build Quality
    "build_quality_mentioned": Noul(
        instructions="Does the reviewer describe an opinion or experience about the phone's materials, sturdiness, or durability?"
    ),
    "build_quality_rating": Score(
        instructions="How satisfied is the reviewer with the build quality?",
        criteria=SATISFACTION_LEVELS,
    ),

    # Value for Money
    "value_for_money_mentioned": Noul(
        instructions="Does the reviewer express whether the phone is worth its price?"
    ),
    "value_for_money_rating": Score(
        instructions="How satisfied is the reviewer with the value for money?",
        criteria=SATISFACTION_LEVELS,
    ),
}