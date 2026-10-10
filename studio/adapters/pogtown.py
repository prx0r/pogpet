"""Pogtown adapter: a character's state change becomes a bounded device intent. Characters never pick colours;
they report how they feel and the device decides how that looks. Mapping lives here, once."""
MOOD = {'happy': 'joy', 'excited': 'joy', 'content': 'calm', 'sleepy': 'calm', 'sad': 'sad', 'grieving': 'sad',
        'worried': 'stressed', 'frustrated': 'stressed', 'amazed': 'surprised', 'curious': 'thinking', 'busy': 'thinking', 'idle': 'neutral'}
class PogtownAdapter:
    def __init__(self, runtime): self.rt = runtime
    def character_event(self, character, mood, intensity=0.6):
        emo = MOOD.get(mood)
        if not emo: return {'ok': False, 'error': f'mood {mood!r} has no device expression', 'hint': 'known: ' + ', '.join(MOOD)}
        return self.rt.invoke('light.express', {'emotion': emo, 'intensity': intensity}, caller='pogtown')
