# Interaction contract

Bartholomew is an interface, not decoration.

## State machine

`idle -> listening -> thinking -> speaking -> idle`

Interruptions may move `speaking -> listening` immediately.
Tool calls can temporarily move to `flying`, `presenting` or `celebrating` and then return to the conversational state.

## Animation rule

The LLM chooses *semantic actions* (`fly_to`, `point_at`, `set_expression`). It never controls individual wing beats or frame timing. The client controller owns micro-animation.

## Reduced motion

If `prefers-reduced-motion: reduce`, disable continuous hover, wing flutter and curved flight. Keep only instant positioning and expression changes.

## Safety / commerce boundary

Visual actions are automatic. State updates are automatic. Paid compute, checkout, emailing, or any irreversible external action requires explicit UI confirmation.
