from modeltranslation.translator import register, TranslationOptions

from ..models import QAEntry

@register(QAEntry)
class QAEntryTranslationOptions(TranslationOptions):
    fields = ('question', 'answer',)