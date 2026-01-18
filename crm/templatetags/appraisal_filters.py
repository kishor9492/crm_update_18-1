from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using a key"""
    if dictionary is None:
        return None
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None

@register.filter
def get_answer_text(existing_answers, question_id):
    """Get answer text from existing answers dict"""
    if existing_answers is None:
        return ''
    answer = existing_answers.get(question_id)
    if answer:
        return answer.answer_text if hasattr(answer, 'answer_text') else ''
    return ''

@register.filter
def get_answer_rating(existing_answers, question_id):
    """Get answer rating from existing answers dict"""
    if existing_answers is None:
        return None
    answer = existing_answers.get(question_id)
    if answer:
        return answer.rating if hasattr(answer, 'rating') else None
    return None

@register.filter(name='has_group')
def has_group(user, group_name):
    """Check if user belongs to a specific group"""
    return user.groups.filter(name=group_name).exists()
