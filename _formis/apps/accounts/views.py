# apps/accounts/views.py
import codecs

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, FormView, TemplateView
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth.forms import PasswordChangeForm
from django.urls import reverse_lazy, reverse
from django.utils.crypto import get_random_string
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from datetime import timedelta
import uuid
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Count
import csv
import secrets
import string

from .forms import LoginForm, ProfileForm, ForgotPasswordForm, ResetPasswordForm, BasicProfileForm, TeacherProfileForm, StudentProfileForm
from .models import Utilisateur, ProfilApprenant, PasswordResetToken

from apps.academic.models import Departement, Classe


class LoginView(FormView):
    """Vue de connexion"""
    template_name = 'auth/login.html'
    form_class = LoginForm

    def dispatch(self, request, *args, **kwargs):
        """Rediriger si déjà connecté"""
        if request.user.is_authenticated:
            return redirect(self.get_success_url_for_user(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Traitement du formulaire valide"""
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        remember_me = self.request.POST.get('remember_me')

        # Essayer d'authentifier par username (matricule)
        user = authenticate(request=self.request, username=username, password=password)
        
        # Si échec, essayer par email
        if user is None:
            try:
                utilisateur = Utilisateur.objects.get(email=username, est_actif=True)
                user = authenticate(request=self.request, username=utilisateur.username, password=password)
            except Utilisateur.DoesNotExist:
                pass

        if user is not None:
            if user.est_actif:
                login(self.request, user)
                
                # Gestion du "Se souvenir de moi"
                if remember_me:
                    # Session expire dans 30 jours
                    self.request.session.set_expiry(30 * 24 * 60 * 60)
                else:
                    # Session expire à la fermeture du navigateur
                    self.request.session.set_expiry(0)

                messages.success(self.request, f"Bienvenue {user.get_full_name()} !")
                
                # Redirection vers la page demandée ou le dashboard
                next_url = self.request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect(self.get_success_url_for_user(user))
            else:
                messages.error(self.request, "Votre compte est désactivé. Contactez l'administration.")
        else:
            messages.error(self.request, "Identifiants incorrects. Vérifiez votre matricule/email et mot de passe.")

        return self.form_invalid(form)

    def get_success_url_for_user(self, user):
        """Retourne l'URL de redirection selon le rôle"""
        return user.get_dashboard_url()

    def get_context_data(self, **kwargs):
        """Ajouter des données au contexte"""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Connexion'
        return context

class LogoutView(LoginRequiredMixin, TemplateView):
    """Vue de déconnexion"""

    def get(self, request, *args, **kwargs):
        user_name = request.user.get_full_name()
        logout(request)
        messages.success(request, f"Au revoir {user_name} ! Vous avez été déconnecté avec succès.")
        return redirect('accounts:login')

class ForgotPasswordView(FormView):
    """Vue pour mot de passe oublié"""
    template_name = 'auth/forgot_password.html'
    form_class = ForgotPasswordForm
    success_url = reverse_lazy('accounts:login')

    def form_valid(self, form):
        email = form.cleaned_data['email']
        try:
            user = Utilisateur.objects.get(email=email, est_actif=True)

            # Supprimer les anciens tokens
            PasswordResetToken.objects.filter(user=user).delete()

            # Créer un nouveau token
            reset_token = PasswordResetToken.objects.create(
                user=user,
                token=get_random_string(50),
                expires_at=timezone.now() + timedelta(hours=24)
            )

            # Envoyer l'email
            self.send_reset_email(user, reset_token.token)
            messages.success(
                self.request,
                "Un email de réinitialisation a été envoyé à votre adresse email. "
                "Vérifiez votre boîte de réception et vos spams."
            )

        except Utilisateur.DoesNotExist:
            # Ne pas révéler si l'email existe ou non pour des raisons de sécurité
            messages.success(
                self.request,
                "Si cette adresse email est associée à un compte, vous recevrez un lien de réinitialisation."
            )

        return super().form_valid(form)

    def send_reset_email(self, user, token):
        """Envoie l'email de réinitialisation"""
        subject = 'Réinitialisation de votre mot de passe - FORMIS'
        reset_url = self.request.build_absolute_uri(
            reverse('accounts:reset_password', kwargs={'token': token})
        )

        context = {
            'user': user,
            'reset_url': reset_url,
            'site_name': 'FORMIS',
        }

        html_message = render_to_string('emails/password_reset.html', context)
        plain_message = strip_tags(html_message)

        try:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:
            messages.error(self.request, "Erreur lors de l'envoi de l'email. Contactez l'administration.")

class ResetPasswordView(FormView):
    """Vue de réinitialisation du mot de passe"""
    template_name = 'auth/reset_password.html'
    form_class = ResetPasswordForm
    success_url = reverse_lazy('accounts:login')

    def dispatch(self, request, *args, **kwargs):
        self.token = kwargs.get('token')
        try:
            self.reset_token = PasswordResetToken.objects.get(token=self.token)
            if self.reset_token.is_expired():
                messages.error(request, "Ce lien de réinitialisation a expiré. Demandez un nouveau lien.")
                return redirect('accounts:forgot_password')
        except PasswordResetToken.DoesNotExist:
            messages.error(request, "Lien de réinitialisation invalide.")
            return redirect('accounts:forgot_password')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        password = form.cleaned_data['password']
        user = self.reset_token.user
        user.set_password(password)
        user.save()

        # Marquer le token comme utilisé
        self.reset_token.mark_as_used()

        messages.success(
            self.request,
            "Votre mot de passe a été réinitialisé avec succès. Vous pouvez maintenant vous connecter."
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['token'] = self.token
        context['user'] = self.reset_token.user
        return context

class ProfileView(LoginRequiredMixin, TemplateView):
    """Vue du profil utilisateur"""
    template_name = 'dashboard/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['user'] = user

        # Informations spécifiques selon le rôle
        if user.role == 'APPRENANT':
            try:
                context['profil_apprenant'] = user.profil_apprenant
                # Ajouter d'autres informations si nécessaire
            except:
                pass

        elif user.role == 'ENSEIGNANT':
            try:
                context['profil_enseignant'] = user.profil_enseignant
                # Ajouter d'autres informations si nécessaire
            except:
                pass

        return context

class EditProfileView(LoginRequiredMixin, UpdateView):
    """Vue de modification du profil"""
    model = Utilisateur
    form_class = ProfileForm
    template_name = 'dashboard/edit_profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Votre profil a été mis à jour avec succès.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier le profil'
        return context

class ChangePasswordView(LoginRequiredMixin, FormView):
    """Vue de changement de mot de passe"""
    template_name = 'dashboard/change_password.html'
    form_class = PasswordChangeForm
    success_url = reverse_lazy('accounts:profile')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Votre mot de passe a été modifié avec succès.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Changer le mot de passe'
        return context

def check_email_availability(request):
    """Vérifie la disponibilité d'un email"""
    email = request.GET.get('email')
    if email:
        exists = Utilisateur.objects.filter(email=email).exists()
        return JsonResponse({'available': not exists})
    return JsonResponse({'available': False})

def generate_password_view(request):
    """Génère un mot de passe aléatoire"""
    password = generate_password()
    return JsonResponse({'password': password})


# ================================
# GESTION DES UTILISATEURS (Admin/Chef département)
# ================================
class UserListView(LoginRequiredMixin, ListView):
    """Liste des utilisateurs (Admin/Chef département)"""
    model = Utilisateur
    template_name = 'accounts/user/list.html'
    context_object_name = 'users'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        # Seuls ADMIN et CHEF_DEPARTEMENT peuvent accéder
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user

        # Filtrer selon le rôle
        if user.role == 'ADMIN':
            # ADMIN voit tous les utilisateurs de son établissement SAUF les APPRENANTS
            queryset = Utilisateur.objects.filter(
                etablissement=user.etablissement
            ).exclude(role='APPRENANT')
        else:  # CHEF_DEPARTEMENT
            # CHEF_DEPARTEMENT voit uniquement les ENSEIGNANTS de son département
            queryset = Utilisateur.objects.filter(
                departement=user.departement,
                role='ENSEIGNANT'
            )

        # Filtres
        role = self.request.GET.get('role')
        if role and role != 'APPRENANT':  # Bloquer le filtre APPRENANT
            queryset = queryset.filter(role=role)

        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(departement_id=departement)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(matricule__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset.select_related('departement').order_by('-date_creation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Adapter les rôles affichables selon l'utilisateur
        if user.role == 'ADMIN':
            context['roles'] = [
                ('ADMIN', 'Administrateur d\'établissement'),
                ('CHEF_DEPARTEMENT', 'Chef de département'),
                ('ENSEIGNANT', 'Enseignant'),
            ]
            context['departements'] = Departement.objects.filter(etablissement=user.etablissement)
        else:  # CHEF_DEPARTEMENT
            context['roles'] = [('ENSEIGNANT', 'Enseignant')]
            context['departements'] = Departement.objects.filter(id=user.departement.id)

        context['current_role'] = self.request.GET.get('role', '')
        context['current_departement'] = self.request.GET.get('departement', '')
        context['search_query'] = self.request.GET.get('search', '')

        return context

class UserCreateView(LoginRequiredMixin, CreateView):
    """Création d'utilisateur"""
    model = Utilisateur
    form_class = BasicProfileForm
    template_name = 'accounts/user/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas créer d'utilisateur. Vérifiez vos permissions.")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_users')
        else:
            return reverse_lazy('dashboard:department_head_users')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_users')
        else:
            return reverse_lazy('dashboard:department_head_users')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter un utilisateur'
        context['submit_text'] = 'Créer'
        context['cancel_url'] = self.get_cancel_url()

        # Limiter les départements selon le rôle
        if self.request.user.role == 'ADMIN':
            context['departements'] = Departement.objects.filter(
                etablissement=self.request.user.etablissement
            )
        else:
            context['departements'] = Departement.objects.filter(
                id=self.request.user.departement.id
            )

        return context

    def form_valid(self, form):
        user = form.save(commit=False)

        # Vérifier si l'utilisateur peut créer ce rôle
        if not self.request.user.peut_creer_role(user.role):
            messages.error(
                self.request,
                f"Vous n'êtes pas autorisé à créer un utilisateur avec le rôle {user.get_role_display()}"
            )
            return self.form_invalid(form)

        # Bloquer explicitement la création d'APPRENANT
        if user.role == 'APPRENANT':
            messages.error(
                self.request,
                "La création d'apprenants n'est pas autorisée via cette interface. "
                "Utilisez la section dédiée aux étudiants."
            )
            return self.form_invalid(form)

        user.etablissement = self.request.user.etablissement
        user.cree_par = self.request.user

        # Si chef de département, assigner automatiquement son département
        if self.request.user.role == 'CHEF_DEPARTEMENT':
            user.departement = self.request.user.departement

        # Génération mot de passe temporaire
        temp_password = generate_password()
        user.set_password(temp_password)

        user.save()

        messages.success(
            self.request,
            f"Utilisateur {user.get_full_name()} créé avec succès. "
            f"Mot de passe temporaire: {temp_password}"
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        """En cas d'erreur de validation"""
        messages.error(self.request, "Erreur lors de la création. Vérifiez les informations saisies.")
        return super().form_invalid(form)

class UserUpdateView(LoginRequiredMixin, UpdateView):
    """Modification d'utilisateur"""
    model = Utilisateur
    form_class = BasicProfileForm
    template_name = 'accounts/user/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas modifier cet utilisateur. Vérifiez vos permissions.")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_users')
        else:
            return reverse_lazy('dashboard:department_head_users')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_users')
        else:
            return reverse_lazy('dashboard:department_head_users')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_users')
        else:
            return redirect('dashboard:department_head_users')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier l\'utilisateur'
        context['submit_text'] = 'Enregistrer'
        context['cancel_url'] = self.get_cancel_url()

        if self.request.user.role == 'ADMIN':
            context['departements'] = Departement.objects.filter(
                etablissement=self.request.user.etablissement
            )
        else:
            context['departements'] = Departement.objects.filter(
                id=self.request.user.departement.id
            )

        return context

    def form_valid(self, form):
        user = form.save(commit=False)

        # Empêcher le changement vers APPRENANT
        if user.role == 'APPRENANT':
            messages.error(
                self.request,
                "Impossible de changer le rôle en APPRENANT via cette interface."
            )
            return self.form_invalid(form)

        # Vérifier que l'utilisateur peut toujours créer ce rôle
        if not self.request.user.peut_creer_role(user.role):
            messages.error(
                self.request,
                f"Vous n'êtes pas autorisé à assigner le rôle {user.get_role_display()}"
            )
            return self.form_invalid(form)

        user.save()
        messages.success(self.request, f"Utilisateur {user.get_full_name()} modifié avec succès.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Erreur lors de la modification. Vérifiez les informations saisies.")
        return super().form_invalid(form)

class UserDetailView(LoginRequiredMixin, DetailView):
    """Détails d'un utilisateur"""
    model = Utilisateur
    template_name = 'accounts/user/detail.html'
    context_object_name = 'user_detail'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Accès non autorisé.")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_users')
        else:
            return reverse_lazy('dashboard:department_head_users')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_users')
        else:
            return redirect('dashboard:department_head_users')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_cancel_url()
        return context

class UserDeleteView(LoginRequiredMixin, DeleteView):
    """Suppression d'utilisateur (désactivation)"""
    model = Utilisateur

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas supprimer cet utilisateur. Vérifiez vos permissions.")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_users')
        else:
            return reverse_lazy('dashboard:department_head_users')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_users')
        else:
            return reverse_lazy('dashboard:department_head_users')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_users')
        else:
            return redirect('dashboard:department_head_users')

    def delete(self, request, *args, **kwargs):
        """Désactivation au lieu de suppression définitive"""
        user = self.get_object()
        user_name = user.get_full_name()

        user.est_actif = False
        user.save()
        messages.success(request, f"Utilisateur {user_name} désactivé avec succès")
        return self.get_success_url()


# ================================
# GESTION DES ENSEIGNANTS
# ================================
class TeacherListView(LoginRequiredMixin, ListView):
    """Liste des enseignants"""
    model = Utilisateur
    template_name = 'accounts/teacher/list.html'
    context_object_name = 'teachers'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user

        if user.role == 'ADMIN':
            queryset = Utilisateur.objects.filter(
                etablissement=user.etablissement,
                role='ENSEIGNANT'
            )
        else:
            queryset = Utilisateur.objects.filter(
                departement=user.departement,
                role='ENSEIGNANT'
            )

        # Filtres
        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(departement_id=departement)

        est_permanent = self.request.GET.get('est_permanent')
        if est_permanent:
            queryset = queryset.filter(profil_enseignant__est_permanent=est_permanent == 'True')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(matricule__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset.select_related('departement', 'profil_enseignant').order_by('-date_creation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.role == 'ADMIN':
            context['departements'] = Departement.objects.filter(etablissement=user.etablissement)
        else:
            context['departements'] = Departement.objects.filter(id=user.departement.id)

        context['current_filters'] = {
            'departement': self.request.GET.get('departement', ''),
            'est_permanent': self.request.GET.get('est_permanent', ''),
            'search': self.request.GET.get('search', ''),
        }
        return context

class TeacherCreateView(LoginRequiredMixin, CreateView):
    """Création d'enseignant"""
    model = Utilisateur
    form_class = TeacherProfileForm
    template_name = 'accounts/teacher/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas créer d'utilisateur. Vérifiez vos permissions.")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_teachers')
        else:
            return reverse_lazy('dashboard:department_head_teachers')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_teachers')
        else:
            return reverse_lazy('dashboard:department_head_teachers')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.role = 'ENSEIGNANT'
        user.etablissement = self.request.user.etablissement
        user.cree_par = self.request.user

        temp_password = generate_password()
        user.set_password(temp_password)

        user.save()
        form.save()  # Sauvegarde les profils associés

        messages.success(
            self.request,
            f"Enseignant {user.get_full_name()} créé avec succès. "
            f"Mot de passe temporaire: {temp_password}"
        )
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter un enseignant'
        context['submit_text'] = 'Créer'
        context['cancel_url'] = self.get_cancel_url()

        if self.request.user.role == 'ADMIN':
            context['departements'] = Departement.objects.filter(
                etablissement=self.request.user.etablissement
            )
        else:
            context['departements'] = Departement.objects.filter(
                id=self.request.user.departement.id
            )

        return context

class TeacherUpdateView(LoginRequiredMixin, UpdateView):
    """Modification d'enseignant"""
    model = Utilisateur
    form_class = TeacherProfileForm
    template_name = 'accounts/teacher/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas modifier cet utilisateur. Vérifiez vos permissions.")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_teachers')
        else:
            return reverse_lazy('dashboard:department_head_teachers')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_teachers')
        else:
            return reverse_lazy('dashboard:department_head_teachers')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_teachers')
        else:
            return redirect('dashboard:department_head_teachers')

    def form_valid(self, form):
        messages.success(self.request, "Enseignant modifié avec succès")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier l\'enseignant'
        context['submit_text'] = 'Enregistrer'
        context['cancel_url'] = self.get_cancel_url()

        if self.request.user.role == 'ADMIN':
            context['departements'] = Departement.objects.filter(
                etablissement=self.request.user.etablissement
            )
        else:
            context['departements'] = Departement.objects.filter(
                id=self.request.user.departement.id
            )

        return context

class TeacherDetailView(LoginRequiredMixin, DetailView):
    """Détails d'un enseignant"""
    model = Utilisateur
    template_name = 'accounts/teacher/detail.html'
    context_object_name = 'teacher'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Accès non autorisé.")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_teachers')
        else:
            return reverse_lazy('dashboard:department_head_teachers')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_teachers')
        else:
            return redirect('dashboard:department_head_teachers')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_cancel_url()
        return context

class TeacherDeleteView(LoginRequiredMixin, DeleteView):
    """Suppression d'enseignant"""
    model = Utilisateur

    def dispatch(self, request, *args, **kwargs):
        teacher = self.get_object()
        if not request.user.peut_gerer_utilisateur(teacher):
            messages.error(request, "Vous ne pouvez pas supprimer cet enseignant. Vérifiez vos permissions.")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_teachers')
        else:
            return reverse_lazy('dashboard:department_head_teachers')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_teachers')
        else:
            return reverse_lazy('dashboard:department_head_teachers')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_teachers')
        else:
            return redirect('dashboard:department_head_teachers')

    def delete(self, request, *args, **kwargs):
        teacher = self.get_object()
        teacher.est_actif = False
        teacher.save()
        messages.success(request, f"Enseignant {teacher.get_full_name()} désactivé avec succès")
        return self.get_success_url()


# ================================
# GESTION DES ÉTUDIANTS
# ================================
class StudentListView(LoginRequiredMixin, ListView):
    """Liste des étudiants"""
    model = Utilisateur
    template_name = 'accounts/student/list.html'
    context_object_name = 'students'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Accès non autorisé")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user

        if user.role == 'ADMIN':
            queryset = Utilisateur.objects.filter(
                etablissement=user.etablissement,
                role='APPRENANT'
            )
        else:
            queryset = Utilisateur.objects.filter(
                departement=user.departement,
                role='APPRENANT'
            )

        # Filtres
        departement = self.request.GET.get('departement')
        if departement:
            queryset = queryset.filter(departement_id=departement)

        classe = self.request.GET.get('classe')
        if classe:
            queryset = queryset.filter(profil_apprenant__classe_actuelle_id=classe)

        statut_paiement = self.request.GET.get('statut_paiement')
        if statut_paiement:
            queryset = queryset.filter(profil_apprenant__statut_paiement=statut_paiement)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(prenom__icontains=search) |
                Q(nom__icontains=search) |
                Q(matricule__icontains=search) |
                Q(email__icontains=search)
            )

        return queryset.select_related('departement', 'profil_apprenant').order_by('-date_creation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.role == 'ADMIN':
            context['departements'] = Departement.objects.filter(etablissement=user.etablissement)
            context['classes'] = Classe.objects.filter(
                niveau__filiere__departement__etablissement=user.etablissement
            )
        else:
            context['departements'] = Departement.objects.filter(id=user.departement.id)
            context['classes'] = Classe.objects.filter(
                niveau__filiere__departement=user.departement
            )

        context['statuts_paiement'] = ProfilApprenant._meta.get_field('statut_paiement').choices
        context['current_filters'] = {
            'departement': self.request.GET.get('departement', ''),
            'classe': self.request.GET.get('classe', ''),
            'statut_paiement': self.request.GET.get('statut_paiement', ''),
            'search': self.request.GET.get('search', ''),
        }
        return context

class StudentCreateView(LoginRequiredMixin, CreateView):
    """Création d'étudiant"""
    model = Utilisateur
    form_class = StudentProfileForm
    template_name = 'accounts/student/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas créer d'apprenant. Vérifiez vos permissions.")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_students')
        else:
            return reverse_lazy('dashboard:department_head_students')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_students')
        else:
            return reverse_lazy('dashboard:department_head_students')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.role = 'APPRENANT'
        user.etablissement = self.request.user.etablissement
        user.cree_par = self.request.user

        temp_password = generate_password()
        user.set_password(temp_password)

        user.save()
        form.save()

        messages.success(
            self.request,
            f"Étudiant {user.get_full_name()} créé avec succès. "
            f"Mot de passe temporaire: {temp_password}"
        )
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ajouter un étudiant'
        context['submit_text'] = 'Créer'
        context['cancel_url'] = self.get_cancel_url()
        return context

class StudentUpdateView(LoginRequiredMixin, UpdateView):
    """Modification d'étudiant"""
    model = Utilisateur
    form_class = StudentProfileForm
    template_name = 'accounts/student/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas modifier cet apprenant. Vérifiez vos permissions.")
            return redirect('dashboard:redirect')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_students')
        else:
            return reverse_lazy('dashboard:department_head_students')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_students')
        else:
            return reverse_lazy('dashboard:department_head_students')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_students')
        else:
            return redirect('dashboard:department_head_students')

    def form_valid(self, form):
        messages.success(self.request, "Étudiant modifié avec succès")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Modifier l\'étudiant'
        context['submit_text'] = 'Enregistrer'
        context['cancel_url'] = self.get_cancel_url()
        return context

class StudentDetailView(LoginRequiredMixin, DetailView):
    """Détails d'un étudiant"""
    model = Utilisateur
    template_name = 'accounts/student/detail.html'
    context_object_name = 'student'

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Accès non autorisé.")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_students')
        else:
            return reverse_lazy('dashboard:department_head_students')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_students')
        else:
            return redirect('dashboard:department_head_students')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_cancel_url()
        return context

class StudentDeleteView(LoginRequiredMixin, DeleteView):
    """Suppression d'étudiant"""
    model = Utilisateur

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
            messages.error(request, "Vous ne pouvez pas supprimer cet apprenant. Vérifiez vos permissions.")
            return self.get_error_redirect()
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_students')
        else:
            return reverse_lazy('dashboard:department_head_students')

    def get_cancel_url(self):
        if self.request.user.role == 'ADMIN':
            return reverse_lazy('dashboard:admin_students')
        else:
            return reverse_lazy('dashboard:department_head_students')

    def get_error_redirect(self):
        if self.request.user.role == 'ADMIN':
            return redirect('dashboard:admin_students')
        else:
            return redirect('dashboard:department_head_students')

    def delete(self, request, *args, **kwargs):
        student = self.get_object()
        student.est_actif = False
        student.save()
        messages.success(request, f"Étudiant {student.get_full_name()} désactivé avec succès")
        return self.get_success_url()


# ================================
# FONCTIONS UTILITAIRES
# ================================
@login_required
def users_export(request):
    """Exporte la liste des utilisateurs en CSV"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        messages.error(request, "Accès non autorisé")
        return redirect('dashboard:redirect')

    # Récupérer les utilisateurs selon le rôle
    if request.user.role == 'ADMIN':
        users = Utilisateur.objects.filter(etablissement=request.user.etablissement)
    else:
        users = Utilisateur.objects.filter(departement=request.user.departement)

    # Appliquer les mêmes filtres que la liste
    role = request.GET.get('role')
    if role:
        users = users.filter(role=role)

    departement = request.GET.get('departement')
    if departement:
        users = users.filter(departement_id=departement)

    search = request.GET.get('search')
    if search:
        users = users.filter(
            Q(prenom__icontains=search) |
            Q(nom__icontains=search) |
            Q(matricule__icontains=search) |
            Q(email__icontains=search)
        )

    users = users.select_related('departement').order_by('-date_creation')

    # Créer le fichier CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="utilisateurs.csv"'
    response.write('\ufeff'.encode('utf8'))  # BOM pour Excel

    writer = csv.writer(response)
    writer.writerow([
        'Matricule', 'Prénom', 'Nom', 'Email', 'Téléphone',
        'Rôle', 'Département', 'Statut', 'Date création'
    ])

    for user in users:
        writer.writerow([
            user.matricule,
            user.prenom,
            user.nom,
            user.email,
            user.telephone or '',
            user.get_role_display(),
            user.departement.nom if user.departement else '',
            'Actif' if user.est_actif else 'Inactif',
            user.date_creation.strftime('%d/%m/%Y %H:%M')
        ])

    return response

@login_required
def export_teachers(request):
    """Exporter les enseignants en CSV"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        return HttpResponse("Non autorisé", status=403)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="enseignants.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Matricule', 'Nom', 'Prénom', 'Email', 'Téléphone',
        'Département', 'Spécialisation', 'Statut', 'Actif'
    ])

    if request.user.role == 'ADMIN':
        teachers = Utilisateur.objects.filter(
            etablissement=request.user.etablissement,
            role='ENSEIGNANT'
        )
    else:
        teachers = Utilisateur.objects.filter(
            departement=request.user.departement,
            role='ENSEIGNANT'
        )

    for teacher in teachers:
        profil = getattr(teacher, 'profil_enseignant', None)
        writer.writerow([
            teacher.matricule,
            teacher.nom,
            teacher.prenom,
            teacher.email,
            teacher.telephone or '',
            teacher.departement.nom if teacher.departement else '',
            profil.specialisation if profil else '',
            'Permanent' if profil and profil.est_permanent else 'Vacataire',
            'Oui' if teacher.est_actif else 'Non'
        ])

    return response

@login_required
def export_students(request):
    """Exporter les étudiants en CSV"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        return HttpResponse("Non autorisé", status=403)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="etudiants.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Matricule', 'Nom', 'Prénom', 'Email', 'Téléphone',
        'Département', 'Classe', 'Statut Paiement', 'Actif'
    ])

    if request.user.role == 'ADMIN':
        students = Utilisateur.objects.filter(
            etablissement=request.user.etablissement,
            role='APPRENANT'
        )
    else:
        students = Utilisateur.objects.filter(
            departement=request.user.departement,
            role='APPRENANT'
        )

    for student in students:
        profil = getattr(student, 'profil_apprenant', None)
        writer.writerow([
            student.matricule,
            student.nom,
            student.prenom,
            student.email,
            student.telephone or '',
            student.departement.nom if student.departement else '',
            profil.classe_actuelle.nom if profil and profil.classe_actuelle else '',
            profil.get_statut_paiement_display() if profil else '',
            'Oui' if student.est_actif else 'Non'
        ])

    return response


@login_required
@require_http_methods(["POST"])
def toggle_user_status(request, pk):
    """Active/Désactive un utilisateur"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    user = get_object_or_404(Utilisateur, pk=pk)

    # Vérifier les permissions
    if request.user.role == 'CHEF_DEPARTEMENT':
        if user.departement != request.user.departement:
            return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    # Empêcher l'auto-désactivation
    if user == request.user:
        return JsonResponse({'success': False, 'error': 'Vous ne pouvez pas vous désactiver vous-même'}, status=400)

    user.est_actif = not user.est_actif
    user.save()

    return JsonResponse({
        'success': True,
        'message': f"Utilisateur {'activé' if user.est_actif else 'désactivé'} avec succès",
        'est_actif': user.est_actif
    })

@login_required
def toggle_teacher_status(request, pk):
    """Toggle statut enseignant"""
    return toggle_user_status(request, pk)

@login_required
def toggle_student_status(request, pk):
    """Toggle statut étudiant"""
    return toggle_user_status(request, pk)


@login_required
@require_http_methods(["POST"])
def admin_reset_password(request, pk):
    """Réinitialise le mot de passe d'un utilisateur"""
    if request.user.role not in ['ADMIN', 'CHEF_DEPARTEMENT']:
        return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    user = get_object_or_404(Utilisateur, pk=pk)

    # Vérifier les permissions
    if request.user.role == 'CHEF_DEPARTEMENT':
        if user.departement != request.user.departement:
            return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    # Générer nouveau mot de passe
    new_password = generate_password()
    user.set_password(new_password)
    user.save()

    # Envoyer email (optionnel)
    try:
        send_mail(
            'Réinitialisation de mot de passe',
            f'Votre nouveau mot de passe temporaire : {new_password}\n\nVeuillez le changer après connexion.',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
        email_sent = True
    except:
        email_sent = False

    return JsonResponse({
        'success': True,
        'message': f'Nouveau mot de passe : {new_password}',
        'email_sent': email_sent
    })


def generate_password():
    """Génère un mot de passe aléatoire sécurisé"""
    import random
    import string

    # 8 caractères : majuscules, minuscules, chiffres, symboles
    chars = string.ascii_letters + string.digits + '@#$%'
    password = ''.join(random.choice(chars) for _ in range(8))

    # S'assurer qu'il contient au moins une majuscule, une minuscule et un chiffre
    if not any(c.isupper() for c in password):
        password = password[:-1] + random.choice(string.ascii_uppercase)
    if not any(c.islower() for c in password):
        password = password[:-2] + random.choice(string.ascii_lowercase) + password[-1]
    if not any(c.isdigit() for c in password):
        password = random.choice(string.digits) + password[1:]

    return password

def generate_password_api(request):
    """API pour générer un mot de passe"""
    password = generate_password()
    return JsonResponse({'password': password})
