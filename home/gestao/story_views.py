from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from home.character_story_models import CharacterStorySubmission
from home.character_stories import (decide_story, edit_ticket, review_ticket, reviewer_allowed,
                                    save_story, story_context, latest_submissions)
from home.models import TbPersonagem
from .views import _workspace


class StoryForm(forms.Form):
    ticket = forms.CharField(widget=forms.HiddenInput)
    text = forms.CharField(label='História', max_length=5000, required=False,
                           widget=forms.Textarea(attrs={'rows': 16, 'maxlength': 5000}))
    action = forms.ChoiceField(choices=[('draft', 'Salvar rascunho'), ('submit', 'Enviar ao Loremaster')])


class ReviewForm(forms.Form):
    ticket = forms.CharField(widget=forms.HiddenInput)
    feedback = forms.CharField(label='Comentário ao jogador', max_length=3000, required=False,
                               widget=forms.Textarea(attrs={'rows': 5, 'maxlength': 3000}))
    action = forms.ChoiceField(choices=[('approved', 'Aprovar história'), ('changes', 'Solicitar ajustes')])


@never_cache
@login_required(login_url='login')
@require_GET
def inbox(request):
    items = latest_submissions(request.user).select_related('character', 'reviewer')
    return render(request, 'home/pages/character_stories_inbox.html', {
        'page_title': 'Histórias dos personagens', 'noindex': True,
        'stories': Paginator(items, 25).get_page(request.GET.get('page'))})


@never_cache
@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def edit(request, pk):
    person = get_object_or_404(TbPersonagem, pk=pk, dono=request.user, arquivado=False)
    if not request.user.is_active:
        raise PermissionDenied
    form = StoryForm(request.POST if request.method == 'POST' else None, initial={
        'text': person.historia or '', 'ticket': edit_ticket(request.user, person)})
    if request.method == 'POST' and form.is_valid():
        try:
            submitted = form.cleaned_data['action'] == 'submit'
            save_story(actor=request.user, character_id=pk, text=form.cleaned_data['text'],
                       ticket=form.cleaned_data['ticket'], submit=submitted)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'História enviada para aprovação.' if submitted else 'Rascunho salvo.')
            return redirect('character_story', pk=pk)
    person.refresh_from_db()
    return render(request, 'home/pages/character_story.html', {
        'page_title': 'História de ' + person.nome, 'noindex': True,
        'p': person, 'form': form, 'story_review': story_context(person),
        'submissions': person.story_submissions.select_related('reviewer').filter(author=request.user)[:10]})


@never_cache
@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def review(request, pk):
    if not reviewer_allowed(request.user):
        raise PermissionDenied
    item = get_object_or_404(CharacterStorySubmission.objects.select_related('character', 'author', 'reviewer'), pk=pk)
    if item.author_id == request.user.pk:
        raise PermissionDenied
    form = ReviewForm(request.POST if request.method == 'POST' else None,
        initial={'ticket': review_ticket(request.user, item)})
    status = 200
    if request.method == 'POST' and form.is_valid():
        try:
            decide_story(actor=request.user, submission_id=pk, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
            status = 409
        else:
            messages.success(request, 'Parecer enviado ao jogador.')
            return redirect('gestao:editorial')
    from home.character_stories import digest
    return render(request, 'home/gestao/story_review.html', _workspace(
        request, 'Revisar história', management_section='editorial', item=item, form=form,
        outdated=digest(item.character.historia) != item.text_digest), status=status)
