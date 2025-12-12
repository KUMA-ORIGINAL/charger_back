from modeltranslation.translator import TranslationOptions, register

from ..models import PageText


@register(PageText)
class PageTextTranslationOptions(TranslationOptions):
    fields = ('text',)
