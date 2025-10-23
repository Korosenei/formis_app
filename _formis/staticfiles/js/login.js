// Fonctionnalité d'affichage/masquage du mot de passe
const passwordToggle = document.getElementById('passwordToggle');
const passwordInput = document.getElementById('password');

passwordToggle.addEventListener('click', function() {
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        passwordToggle.innerHTML = '<i class="fas fa-eye-slash"></i>';
    } else {
        passwordInput.type = 'password';
        passwordToggle.innerHTML = '<i class="fas fa-eye"></i>';
    }
});

// Gestion de la soumission du formulaire
const loginForm = document.getElementById('loginForm');
const errorMessage = document.getElementById('errorMessage');
const errorText = document.getElementById('errorText');
const submitButton = document.getElementById('submitButton');

loginForm.addEventListener('submit', function(e) {
    e.preventDefault();
    
    // Simulation de chargement
    submitButton.innerHTML = '<span class="loading"></span> Connexion...';
    submitButton.disabled = true;
    
    // Récupération des valeurs du formulaire
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    // Simulation d'une requête AJAX
    setTimeout(() => {
        // Ici, normalement, vous auriez une requête vers votre backend
        // Pour cet exemple, nous allons simuler une erreur
        showError("Identifiants incorrects. Veuillez réessayer.");
        
        // Réactiver le bouton
        submitButton.innerHTML = '<i class="fas fa-sign-in-alt"></i> Se connecter';
        submitButton.disabled = false;
    }, 1500);
});

// Fonction pour afficher les erreurs
function showError(message) {
    errorText.textContent = message;
    errorMessage.style.display = 'flex';
}

// Gestion du modal de mot de passe oublié
const forgotPasswordLink = document.getElementById('forgotPasswordLink');
const forgotPasswordModal = document.getElementById('forgotPasswordModal');
const closeModal = document.getElementById('closeModal');
const forgotPasswordForm = document.getElementById('forgotPasswordForm');

forgotPasswordLink.addEventListener('click', function(e) {
    e.preventDefault();
    forgotPasswordModal.style.display = 'flex';
});

closeModal.addEventListener('click', function() {
    forgotPasswordModal.style.display = 'none';
});

// Fermer le modal en cliquant à l'extérieur
window.addEventListener('click', function(e) {
    if (e.target === forgotPasswordModal) {
        forgotPasswordModal.style.display = 'none';
    }
});

// Soumission du formulaire de mot de passe oublié
forgotPasswordForm.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const email = document.getElementById('email').value;
    
    // Ici, vous enverriez normalement une requête à votre backend
    alert(`Un lien de réinitialisation a été envoyé à ${email} (simulation)`);
    forgotPasswordModal.style.display = 'none';
});

// Focus automatique sur le champ username au chargement
document.getElementById('username').focus();