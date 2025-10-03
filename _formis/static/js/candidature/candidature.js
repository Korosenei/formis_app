/**
 * Système de gestion du formulaire de candidature
 * Version: 1.0.0
 * Description: Gère la navigation multi-étapes, la validation, l'upload de documents
 * et les appels API pour un formulaire de candidature académique
 */

class CandidatureForm {
  constructor() {
    this.currentStep = 1;
    this.maxStep = 4;
    this.formData = {
      formation: {},
      personal: {},
      academic: {},
      documents: {},
      files: new Map(),
    };
    this.documentsRequis = [];
    this.validators = {};
    this.isSubmitting = false;

    this.init();
  }

  /**
   * Initialisation du formulaire
   */
  init() {
    this.bindEvents();
    this.initializeValidation();
    this.updateProgressBar();
    this.setupFormPersistence();

    // Charger les données sauvegardées s'il y en a
    this.loadSavedData();

    console.log("Formulaire de candidature initialisé");
  }

  /**
   * Liaison des événements
   */
  bindEvents() {
    // Navigation
    const nextBtn = document.getElementById("next-btn");
    const prevBtn = document.getElementById("prev-btn");
    const submitBtn = document.getElementById("submit-btn");
    const saveDraftBtn = document.getElementById("save-draft-btn");

    nextBtn?.addEventListener("click", () => this.nextStep());
    prevBtn?.addEventListener("click", () => this.prevStep());
    submitBtn?.addEventListener("click", (e) => this.handleSubmit(e));
    saveDraftBtn?.addEventListener("click", () => this.saveDraft());

    // Charger les établissements et années académiques au démarrage
    this.loadEtablissements();
    this.loadAnneesAcademiques();

    // Gestion des changements de sélection pour les listes dépendantes
    this.setupDependentSelects();

    // Gestion des uploads de fichiers
    this.setupFileUploads();

    // Validation en temps réel
    this.setupRealTimeValidation();

    // Gestion du redimensionnement de la fenêtre
    window.addEventListener(
      "resize",
      this.debounce(() => {
        this.updateLayout();
      }, 250)
    );

    // Prévention de la perte de données
    window.addEventListener("beforeunload", (e) => {
      if (this.hasUnsavedChanges()) {
        e.preventDefault();
        e.returnValue =
          "Vous avez des modifications non sauvegardées. Êtes-vous sûr de vouloir quitter ?";
        return e.returnValue;
      }
    });
  }

  /**
   * Configuration des listes dépendantes (établissement > département > filière > niveau)
   */
  setupDependentSelects() {
    const etablissementSelect = document.getElementById("etablissement");
    const departementSelect = document.getElementById("departement");
    const filiereSelect = document.getElementById("filiere");
    const niveauSelect = document.getElementById("niveau");

    etablissementSelect?.addEventListener("change", async (e) => {
      const etablissementId = e.target.value;
      if (etablissementId) {
        await this.loadDepartements(etablissementId);
        this.resetSelect(filiereSelect, "Sélectionnez d'abord un département");
        this.resetSelect(niveauSelect, "Sélectionnez d'abord une filière");
      } else {
        this.resetSelect(
          departementSelect,
          "Sélectionnez d'abord un établissement"
        );
        this.resetSelect(filiereSelect, "Sélectionnez d'abord un département");
        this.resetSelect(niveauSelect, "Sélectionnez d'abord une filière");
      }
    });

    departementSelect?.addEventListener("change", async (e) => {
      const departementId = e.target.value;
      if (departementId) {
        await this.loadFilieres(departementId);
        this.resetSelect(niveauSelect, "Sélectionnez d'abord une filière");
      } else {
        this.resetSelect(filiereSelect, "Sélectionnez d'abord un département");
        this.resetSelect(niveauSelect, "Sélectionnez d'abord une filière");
      }
    });

    filiereSelect?.addEventListener("change", async (e) => {
      const filiereId = e.target.value;
      if (filiereId) {
        await this.loadNiveaux(filiereId);
        await this.loadDocumentsRequis(filiereId);
      } else {
        this.resetSelect(niveauSelect, "Sélectionnez d'abord une filière");
      }
    });

    niveauSelect?.addEventListener("change", async (e) => {
      const niveauId = e.target.value;
      if (niveauId) {
        // Filtrer les documents selon le niveau si nécessaire
        await this.filterDocumentsByNiveau(niveauId);
      }
    });
  }

  /**
   * Chargement des établissements
   */
  async loadEtablissements() {
    try {
      this.showLoading(true);

      const response = await fetch(
        "/establishments/api/public/etablissements/"
      );

      if (!response.ok) {
        throw new Error(`Erreur HTTP: ${response.status}`);
      }

      const data = await response.json();

      if (data.success && data.results) {
        this.populateSelect(
          "etablissement",
          data.results,
          "nom",
          "id",
          "Sélectionnez un établissement"
        );
        console.log(`${data.count} établissements chargés`);
      } else {
        this.showMessage(
          "error",
          "Erreur lors du chargement des établissements"
        );
      }
    } catch (error) {
      console.error("Erreur lors du chargement des établissements:", error);
      this.showMessage(
        "error",
        "Impossible de charger les établissements. Veuillez recharger la page."
      );
    } finally {
      this.showLoading(false);
    }
  }

  /**
   * Chargement des années académiques
   */
  async loadAnneesAcademiques() {
    try {
      const response = await fetch(
        "/establishments/api/public/annees-academiques/"
      );

      if (!response.ok) {
        // Si l'endpoint n'existe pas, utiliser des années par défaut
        console.warn(
          "Endpoint années académiques non disponible, utilisation d'années par défaut"
        );
        this.useDefaultAnneesAcademiques();
        return;
      }

      const data = await response.json();

      if (data.success && data.results) {
        this.populateSelect(
          "annee_academique",
          data.results,
          "nom",
          "id",
          "Sélectionnez l'année"
        );
        console.log(`${data.count} années académiques chargées`);
      } else {
        this.useDefaultAnneesAcademiques();
      }
    } catch (error) {
      console.warn(
        "Erreur lors du chargement des années académiques, utilisation des valeurs par défaut:",
        error
      );
      this.useDefaultAnneesAcademiques();
    }
  }

  /**
   * Utilisation d'années académiques par défaut
   */
  useDefaultAnneesAcademiques() {
    const currentYear = new Date().getFullYear();
    const defaultYears = [
      {
        id: `${currentYear}-${currentYear + 1}`,
        nom: `${currentYear}-${currentYear + 1}`,
      },
      {
        id: `${currentYear + 1}-${currentYear + 2}`,
        nom: `${currentYear + 1}-${currentYear + 2}`,
      },
    ];

    this.populateSelect(
      "annee_academique",
      defaultYears,
      "nom",
      "id",
      "Sélectionnez l'année"
    );
    console.log("Années académiques par défaut chargées");
  }

  /**
   * Chargement des départements par établissement
   */
  async loadDepartements(etablissementId) {
    try {
      this.showLoading(true);

      const response = await fetch(
        `/academic/api/public/departements/${etablissementId}/`
      );

      if (!response.ok) {
        throw new Error(`Erreur HTTP: ${response.status}`);
      }

      const data = await response.json();

      if (data.success && data.results) {
        this.populateSelect(
          "departement",
          data.results,
          "nom",
          "id",
          "Sélectionnez un département"
        );
        document.getElementById("departement").disabled = false;
        console.log(
          `${data.count} départements chargés pour ${data.etablissement?.nom}`
        );
      } else {
        this.showMessage("error", "Erreur lors du chargement des départements");
      }
    } catch (error) {
      console.error("Erreur lors du chargement des départements:", error);
      this.showMessage(
        "error",
        "Impossible de charger les départements. Veuillez réessayer."
      );
    } finally {
      this.showLoading(false);
    }
  }

  /**
   * Chargement des filières par département
   */
  async loadFilieres(departementId) {
    try {
      this.showLoading(true);

      const response = await fetch(
        `/academic/api/public/filieres/${departementId}/`
      );

      if (!response.ok) {
        throw new Error(`Erreur HTTP: ${response.status}`);
      }

      const data = await response.json();

      if (data.success && data.results) {
        this.populateSelect(
          "filiere",
          data.results,
          "nom",
          "id",
          "Sélectionnez une filière"
        );
        document.getElementById("filiere").disabled = false;
        console.log(
          `${data.count} filières chargées pour ${data.departement?.nom}`
        );
      } else {
        this.showMessage("error", "Erreur lors du chargement des filières");
      }
    } catch (error) {
      console.error("Erreur lors du chargement des filières:", error);
      this.showMessage(
        "error",
        "Impossible de charger les filières. Veuillez réessayer."
      );
    } finally {
      this.showLoading(false);
    }
  }

  /**
   * Chargement des niveaux par filière
   */
  async loadNiveaux(filiereId) {
    try {
      this.showLoading(true);

      const response = await fetch(
        `/academic/api/public/niveaux/${filiereId}/`
      );

      if (!response.ok) {
        throw new Error(`Erreur HTTP: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        // Vérifier si la réponse a des niveaux ou utiliser un format générique
        let niveaux = [];

        if (data.results) {
          niveaux = data.results;
        } else if (data.data && data.data.niveaux) {
          niveaux = data.data.niveaux;
        } else {
          // Si pas de niveaux spécifiques, créer des niveaux génériques
          const filiere = data.filiere || data.data?.filiere;
          if (filiere && filiere.duree_annees) {
            for (let i = 1; i <= filiere.duree_annees; i++) {
              niveaux.push({
                id: `niveau-${i}`,
                nom: `${i}ème année`,
                code: `ANNEE${i}`,
              });
            }
          } else {
            // Niveaux par défaut
            niveaux = [
              { id: "niveau-1", nom: "1ère année", code: "ANNEE1" },
              { id: "niveau-2", nom: "2ème année", code: "ANNEE2" },
              { id: "niveau-3", nom: "3ème année", code: "ANNEE3" },
            ];
          }
        }

        this.populateSelect(
          "niveau",
          niveaux,
          "nom",
          "id",
          "Sélectionnez un niveau"
        );
        document.getElementById("niveau").disabled = false;
        console.log(`${niveaux.length} niveaux chargés`);
      } else {
        this.showMessage("error", "Erreur lors du chargement des niveaux");
      }
    } catch (error) {
      console.error("Erreur lors du chargement des niveaux:", error);
      this.showMessage(
        "error",
        "Impossible de charger les niveaux. Veuillez réessayer."
      );
    } finally {
      this.showLoading(false);
    }
  }

  /**
   * Chargement des documents requis par filière
   */
  async loadDocumentsRequis(filiereId) {
    try {
      this.showLoading(true);

      const response = await fetch(
        `/enrollment/public/api/documents_by_filiere/${filiereId}/`
      );

      if (!response.ok) {
        throw new Error(`Erreur HTTP: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        this.documentsRequis = data.data.documents_requis || [];
        this.renderDocumentsSection();
        console.log(
          `${data.data.total} documents requis chargés pour ${data.data.filiere?.nom}`
        );

        if (this.documentsRequis.length === 0) {
          this.showMessage(
            "info",
            "Aucun document spécifique requis pour cette filière"
          );
        }
      } else {
        this.showMessage(
          "error",
          data.message || "Erreur lors du chargement des documents requis"
        );
      }
    } catch (error) {
      console.error("Erreur lors du chargement des documents:", error);
      this.showMessage(
        "error",
        "Impossible de charger la liste des documents requis."
      );
    } finally {
      this.showLoading(false);
    }
  }

  /**
   * Peuple une liste déroulante avec des données
   */
  populateSelect(selectId, items, labelField, valueField, placeholderText) {
    const select = document.getElementById(selectId);
    if (!select) return;

    // Vider les options existantes
    select.innerHTML = `<option value="">${placeholderText}</option>`;

    // Ajouter les nouvelles options
    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item[valueField];
      option.textContent = item[labelField];
      select.appendChild(option);
    });
  }

  /**
   * Remet à zéro une liste déroulante
   */
  resetSelect(select, placeholderText) {
    if (!select) return;

    select.innerHTML = `<option value="">${placeholderText}</option>`;
    select.disabled = true;
    select.classList.remove("error", "success");

    // Effacer les messages d'erreur
    const errorDiv = select.nextElementSibling;
    if (errorDiv && errorDiv.classList.contains("form-error")) {
      errorDiv.textContent = "";
      errorDiv.classList.remove("active");
    }
  }

  /**
   * Rendu de la section documents
   */
  renderDocumentsSection() {
    const container = document.getElementById("documents-container");
    if (!container) return;

    container.innerHTML = "";

    this.documentsRequis.forEach((doc) => {
      const documentItem = this.createDocumentItem(doc);
      container.appendChild(documentItem);
    });
  }

  /**
   * Création d'un élément document
   */
  createDocumentItem(doc) {
    const item = document.createElement("div");
    item.className = `document-item ${doc.est_obligatoire ? "required" : ""}`;
    item.dataset.documentType = doc.type_document;

    item.innerHTML = `
            <div class="document-header">
                <h4 class="document-title ${
                  doc.est_obligatoire ? "required" : ""
                }">
                    ${doc.nom}
                </h4>
                <span class="document-status ${
                  doc.est_obligatoire ? "required" : "optional"
                }">
                    ${doc.est_obligatoire ? "Obligatoire" : "Optionnel"}
                </span>
            </div>
            
            ${
              doc.description
                ? `<p class="document-description">${doc.description}</p>`
                : ""
            }
            
            <div class="file-upload-zone" data-document-type="${
              doc.type_document
            }">
                <div class="upload-icon">📄</div>
                <p class="upload-text">Cliquez pour sélectionner un fichier ou glissez-déposez</p>
                <p class="upload-hint">
                    Formats acceptés: ${doc.formats_autorises
                      .join(", ")
                      .toUpperCase()} 
                    (max ${this.formatFileSize(doc.taille_maximale)})
                </p>
                <input type="file" class="file-input" 
                       data-document-type="${doc.type_document}"
                       accept="${doc.formats_autorises
                         .map((f) => "." + f)
                         .join(",")}"
                       data-max-size="${doc.taille_maximale}">
            </div>
            
            <div class="uploaded-files"></div>
        `;

    // Ajouter les événements pour cet élément
    this.setupDocumentItemEvents(item, doc);

    return item;
  }

  /**
   * Configuration des événements pour un élément document
   */
  setupDocumentItemEvents(item, doc) {
    const uploadZone = item.querySelector(".file-upload-zone");
    const fileInput = item.querySelector(".file-input");

    // Clic sur la zone d'upload
    uploadZone.addEventListener("click", () => {
      fileInput.click();
    });

    // Changement de fichier
    fileInput.addEventListener("change", (e) => {
      this.handleFileSelection(e, doc);
    });

    // Glisser-déposer
    uploadZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadZone.classList.add("dragover");
    });

    uploadZone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      uploadZone.classList.remove("dragover");
    });

    uploadZone.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadZone.classList.remove("dragover");

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        fileInput.files = files;
        this.handleFileSelection({ target: fileInput }, doc);
      }
    });
  }

  /**
   * Gestion de la sélection de fichier
   */
  handleFileSelection(event, doc) {
    const file = event.target.files[0];
    if (!file) return;

    // Validation du fichier
    const validation = this.validateFile(file, doc);
    if (!validation.valid) {
      this.showMessage("error", validation.message);
      event.target.value = ""; // Reset du champ
      return;
    }

    // Stocker le fichier
    this.formData.files.set(doc.type_document, file);

    // Mettre à jour l'affichage
    this.displayUploadedFile(event.target.closest(".document-item"), file, doc);

    // Marquer le document comme uploadé
    const documentItem = event.target.closest(".document-item");
    documentItem.classList.add("uploaded");

    // Mettre à jour le statut
    const statusElement = documentItem.querySelector(".document-status");
    statusElement.textContent = "Téléchargé";
    statusElement.className = "document-status uploaded";

    this.showMessage("success", `Document "${doc.nom}" ajouté avec succès`);
  }

  /**
   * Validation d'un fichier
   */
  validateFile(file, doc) {
    // Vérification de la taille
    if (file.size > doc.taille_maximale) {
      return {
        valid: false,
        message: `Le fichier est trop volumineux. Taille maximale: ${this.formatFileSize(
          doc.taille_maximale
        )}`,
      };
    }

    // Vérification du format
    const extension = file.name.split(".").pop().toLowerCase();
    if (!doc.formats_autorises.includes(extension)) {
      return {
        valid: false,
        message: `Format de fichier non autorisé. Formats acceptés: ${doc.formats_autorises
          .join(", ")
          .toUpperCase()}`,
      };
    }

    return { valid: true };
  }

  /**
   * Affichage d'un fichier uploadé
   */
  displayUploadedFile(documentItem, file, doc) {
    const uploadedFilesContainer =
      documentItem.querySelector(".uploaded-files");

    // Supprimer l'ancien fichier s'il existe
    uploadedFilesContainer.innerHTML = "";

    const fileElement = document.createElement("div");
    fileElement.className = "uploaded-file";
    fileElement.innerHTML = `
            <div class="file-icon">📎</div>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-size">${this.formatFileSize(file.size)}</div>
            </div>
            <div class="file-actions">
                <button type="button" class="btn-icon-only" title="Prévisualiser" onclick="candidatureForm.previewFile('${
                  doc.type_document
                }')">
                    👁️
                </button>
                <button type="button" class="btn-icon-only danger" title="Supprimer" onclick="candidatureForm.removeFile('${
                  doc.type_document
                }')">
                    🗑️
                </button>
            </div>
        `;

    uploadedFilesContainer.appendChild(fileElement);

    // Masquer la zone d'upload
    const uploadZone = documentItem.querySelector(".file-upload-zone");
    uploadZone.style.display = "none";
  }

  /**
   * Suppression d'un fichier
   */
  removeFile(documentType) {
    if (confirm("Êtes-vous sûr de vouloir supprimer ce document ?")) {
      this.formData.files.delete(documentType);

      const documentItem = document
        .querySelector(`[data-document-type="${documentType}"]`)
        .closest(".document-item");
      documentItem.classList.remove("uploaded");

      // Remettre à zéro l'affichage
      const uploadedFilesContainer =
        documentItem.querySelector(".uploaded-files");
      uploadedFilesContainer.innerHTML = "";

      const uploadZone = documentItem.querySelector(".file-upload-zone");
      uploadZone.style.display = "block";

      // Remettre à zéro le champ file
      const fileInput = documentItem.querySelector(".file-input");
      fileInput.value = "";

      // Mettre à jour le statut
      const doc = this.documentsRequis.find(
        (d) => d.type_document === documentType
      );
      const statusElement = documentItem.querySelector(".document-status");
      statusElement.textContent = doc?.est_obligatoire
        ? "Obligatoire"
        : "Optionnel";
      statusElement.className = `document-status ${
        doc?.est_obligatoire ? "required" : "optional"
      }`;

      this.showMessage("info", "Document supprimé");
    }
  }

  /**
   * Prévisualisation d'un fichier
   */
  previewFile(documentType) {
    const file = this.formData.files.get(documentType);
    if (!file) return;

    if (file.type.startsWith("image/")) {
      // Prévisualisation d'image
      const reader = new FileReader();
      reader.onload = (e) => {
        this.showImagePreview(e.target.result, file.name);
      };
      reader.readAsDataURL(file);
    } else if (file.type === "application/pdf") {
      // Ouvrir le PDF dans un nouvel onglet
      const url = URL.createObjectURL(file);
      window.open(url, "_blank");
    } else {
      this.showMessage(
        "info",
        "Prévisualisation non disponible pour ce type de fichier"
      );
    }
  }

  /**
   * Affichage de la prévisualisation d'image
   */
  showImagePreview(imageSrc, fileName) {
    const modal = document.createElement("div");
    modal.className = "preview-modal";
    modal.innerHTML = `
            <div class="preview-content">
                <div class="preview-header">
                    <h3>${fileName}</h3>
                    <button type="button" class="close-btn" onclick="this.closest('.preview-modal').remove()">×</button>
                </div>
                <div class="preview-body">
                    <img src="${imageSrc}" alt="${fileName}" style="max-width: 100%; max-height: 70vh; object-fit: contain;">
                </div>
            </div>
        `;

    // Styles inline pour la modal
    modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
        `;

    const content = modal.querySelector(".preview-content");
    content.style.cssText = `
            background: white;
            border-radius: 8px;
            max-width: 90vw;
            max-height: 90vh;
            overflow: hidden;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        `;

    const header = modal.querySelector(".preview-header");
    header.style.cssText = `
            padding: 1rem;
            border-bottom: 1px solid #e5e5e5;
            display: flex;
            justify-content: space-between;
            align-items: center;
        `;

    const closeBtn = modal.querySelector(".close-btn");
    closeBtn.style.cssText = `
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            padding: 0.5rem;
        `;

    const body = modal.querySelector(".preview-body");
    body.style.cssText = `
            padding: 1rem;
            text-align: center;
        `;

    document.body.appendChild(modal);

    // Fermeture au clic sur l'arrière-plan
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.remove();
      }
    });
  }

  /**
   * Configuration des uploads de fichiers
   */
  setupFileUploads() {
    // Cette méthode sera appelée après le rendu des documents
    // Les événements sont configurés dans setupDocumentItemEvents
  }

  /**
   * Configuration de la validation en temps réel
   */
  setupRealTimeValidation() {
    const form = document.getElementById("candidature-form");
    if (!form) return;

    // Validation sur changement pour tous les champs
    form.addEventListener("input", (e) => {
      if (e.target.matches("input, select, textarea")) {
        this.validateField(e.target);
      }
    });

    // Validation sur perte de focus
    form.addEventListener(
      "blur",
      (e) => {
        if (e.target.matches("input, select, textarea")) {
          this.validateField(e.target);
        }
      },
      true
    );
  }

  /**
   * Initialisation des validateurs
   */
  initializeValidation() {
    this.validators = {
      required: (value) => {
        return value.toString().trim().length > 0
          ? null
          : "Ce champ est obligatoire";
      },

      email: (value) => {
        if (!value) return null;
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(value) ? null : "Adresse email invalide";
      },

      telephone: (value) => {
        if (!value) return null;
        const phoneRegex = /^(\+226|00226|226)?[0-9]{8}$/;
        const cleanValue = value.replace(/\s+/g, "");
        return phoneRegex.test(cleanValue)
          ? null
          : "Numéro de téléphone invalide (format: +226 XX XX XX XX)";
      },

      date: (value) => {
        if (!value) return null;
        const date = new Date(value);
        const today = new Date();

        if (isNaN(date.getTime())) {
          return "Date invalide";
        }

        // Pour la date de naissance, vérifier l'âge
        if (value.includes("date_naissance")) {
          const age = today.getFullYear() - date.getFullYear();
          if (age < 15) return "Âge minimum requis: 15 ans";
          if (age > 100) return "Veuillez vérifier la date de naissance";
          if (date > today) return "La date ne peut pas être dans le futur";
        }

        return null;
      },

      annee: (value) => {
        if (!value) return null;
        const annee = parseInt(value);
        const currentYear = new Date().getFullYear();

        if (annee < 1950 || annee > currentYear) {
          return `L'année doit être entre 1950 et ${currentYear}`;
        }

        return null;
      },
    };
  }

  /**
   * Validation d'un champ
   */
  validateField(field) {
    const value = field.value;
    const fieldName = field.name;
    const isRequired = field.hasAttribute("required");

    let error = null;

    // Validation obligatoire
    if (isRequired && this.validators.required(value)) {
      error = this.validators.required(value);
    }

    // Validations spécifiques
    if (!error && value) {
      if (field.type === "email") {
        error = this.validators.email(value);
      } else if (field.type === "tel" || fieldName.includes("telephone")) {
        error = this.validators.telephone(value);
      } else if (field.type === "date") {
        error = this.validators.date(value);
      } else if (fieldName === "annee_obtention") {
        error = this.validators.annee(value);
      }
    }

    // Affichage du résultat
    this.displayFieldValidation(field, error);

    return !error;
  }

  /**
   * Affichage de la validation d'un champ
   */
  displayFieldValidation(field, error) {
    const errorDiv = field.nextElementSibling;

    // Supprimer les classes d'état précédentes
    field.classList.remove("error", "success");

    if (error) {
      field.classList.add("error");
      if (errorDiv && errorDiv.classList.contains("form-error")) {
        errorDiv.textContent = error;
        errorDiv.classList.add("active");
      }
    } else if (field.value) {
      field.classList.add("success");
      if (errorDiv && errorDiv.classList.contains("form-error")) {
        errorDiv.textContent = "";
        errorDiv.classList.remove("active");
      }
    }
  }

  /**
   * Navigation vers l'étape suivante
   */
  nextStep() {
    if (this.currentStep >= this.maxStep) return;

    if (this.validateCurrentStep()) {
      this.saveCurrentStepData();
      this.currentStep++;
      this.updateStep();
    }
  }

  /**
   * Navigation vers l'étape précédente
   */
  prevStep() {
    if (this.currentStep <= 1) return;

    this.saveCurrentStepData();
    this.currentStep--;
    this.updateStep();
  }

  /**
   * Validation de l'étape courante
   */
  validateCurrentStep() {
    const currentStepElement = document.getElementById(
      `step-${this.currentStep}`
    );
    if (!currentStepElement) return false;

    const fields = currentStepElement.querySelectorAll(
      "input[required], select[required], textarea[required]"
    );
    let isValid = true;

    fields.forEach((field) => {
      if (!this.validateField(field)) {
        isValid = false;
      }
    });

    // Validations spécifiques par étape
    if (this.currentStep === 3) {
      // Vérifier que tous les documents obligatoires sont fournis
      const missingDocs = this.getMissingRequiredDocuments();
      if (missingDocs.length > 0) {
        this.showMessage(
          "error",
          `Documents obligatoires manquants: ${missingDocs.join(", ")}`
        );
        isValid = false;
      }
    }

    if (!isValid) {
      this.showMessage(
        "error",
        "Veuillez corriger les erreurs avant de continuer"
      );
    }

    return isValid;
  }

  /**
   * Obtenir la liste des documents obligatoires manquants
   */
  getMissingRequiredDocuments() {
    const missing = [];

    this.documentsRequis.forEach((doc) => {
      if (doc.est_obligatoire && !this.formData.files.has(doc.type_document)) {
        missing.push(doc.nom);
      }
    });

    return missing;
  }

  /**
   * Mise à jour de l'affichage de l'étape
   */
  updateStep() {
    // Masquer toutes les étapes
    document.querySelectorAll(".form-step").forEach((step) => {
      step.classList.remove("active");
    });

    // Afficher l'étape courante
    const currentStepElement = document.getElementById(
      `step-${this.currentStep}`
    );
    if (currentStepElement) {
      currentStepElement.classList.add("active");
    }

    // Mettre à jour la barre de progression
    this.updateProgressBar();

    // Mettre à jour les boutons
    this.updateNavigationButtons();

    // Générer le résumé si c'est la dernière étape
    if (this.currentStep === this.maxStep) {
      this.generateSummary();
    }

    // Scroll vers le haut
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /**
   * Mise à jour de la barre de progression
   */
  updateProgressBar() {
    document.querySelectorAll(".progress-step").forEach((step, index) => {
      const stepNumber = index + 1;
      step.classList.remove("active", "completed");

      if (stepNumber < this.currentStep) {
        step.classList.add("completed");
      } else if (stepNumber === this.currentStep) {
        step.classList.add("active");
      }
    });
  }

  /**
   * Mise à jour des boutons de navigation
   */
  updateNavigationButtons() {
    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    const submitBtn = document.getElementById("submit-btn");

    // Bouton précédent
    if (prevBtn) {
      prevBtn.style.display = this.currentStep > 1 ? "flex" : "none";
    }

    // Boutons suivant/soumettre
    if (this.currentStep === this.maxStep) {
      if (nextBtn) nextBtn.style.display = "none";
      if (submitBtn) submitBtn.style.display = "flex";
    } else {
      if (nextBtn) nextBtn.style.display = "flex";
      if (submitBtn) submitBtn.style.display = "none";
    }
  }

  /**
   * Sauvegarde des données de l'étape courante
   */
  saveCurrentStepData() {
    const currentStepElement = document.getElementById(
      `step-${this.currentStep}`
    );
    if (!currentStepElement) return;

    const inputs = currentStepElement.querySelectorAll(
      "input, select, textarea"
    );

    inputs.forEach((input) => {
      if (input.type === "file" || !input.name || !input.value) return;

      // Déterminer la section de données selon l'étape
      let dataSection;
      switch (this.currentStep) {
        case 1:
          dataSection = this.formData.formation;
          break;
        case 2:
          dataSection = this.formData.personal;
          break;
        case 3:
          // Les fichiers sont gérés séparément
          return;
        default:
          dataSection = this.formData.academic;
      }

      dataSection[input.name] = input.value;
    });

    console.log(
      `Données sauvegardées pour étape ${this.currentStep}:`,
      this.currentStep === 1
        ? this.formData.formation
        : this.currentStep === 2
        ? this.formData.personal
        : this.formData.academic
    );
  }

  /**
   * Génération du résumé pour validation
   */
  generateSummary() {
    const container = document.getElementById("summary-container");
    if (!container) return;

    // Sauvegarder les données courantes
    this.saveCurrentStepData();

    container.innerHTML = `
            <div class="summary-section">
                <h3 class="summary-title">Formation choisie</h3>
                <div class="summary-grid">
                    ${this.createSummaryItem(
                      "Établissement",
                      this.getSelectOptionText("etablissement")
                    )}
                    ${this.createSummaryItem(
                      "Département",
                      this.getSelectOptionText("departement")
                    )}
                    ${this.createSummaryItem(
                      "Filière",
                      this.getSelectOptionText("filiere")
                    )}
                    ${this.createSummaryItem(
                      "Niveau",
                      this.getSelectOptionText("niveau")
                    )}
                    ${this.createSummaryItem(
                      "Année académique",
                      this.getSelectOptionText("annee_academique")
                    )}
                </div>
            </div>

            <div class="summary-section">
                <h3 class="summary-title">Informations personnelles</h3>
                <div class="summary-grid">
                    ${this.createSummaryItem(
                      "Nom complet",
                      `${this.formData.personal.prenom || ""} ${
                        this.formData.personal.nom || ""
                      }`.trim()
                    )}
                    ${this.createSummaryItem(
                      "Date de naissance",
                      this.formatDate(this.formData.personal.date_naissance)
                    )}
                    ${this.createSummaryItem(
                      "Lieu de naissance",
                      this.formData.personal.lieu_naissance
                    )}
                    ${this.createSummaryItem(
                      "Genre",
                      this.formData.personal.genre === "M"
                        ? "Masculin"
                        : "Féminin"
                    )}
                    ${this.createSummaryItem(
                      "Téléphone",
                      this.formData.personal.telephone
                    )}
                    ${this.createSummaryItem(
                      "Email",
                      this.formData.personal.email
                    )}
                    ${this.createSummaryItem(
                      "Adresse",
                      this.formData.personal.adresse
                    )}
                </div>
            </div>

            <div class="summary-section">
                <h3 class="summary-title">Documents fournis</h3>
                <div class="documents-summary">
                    ${this.generateDocumentsSummary()}
                </div>
            </div>
        `;
  }

  /**
   * Création d'un élément de résumé
   */
  createSummaryItem(label, value) {
    return `
            <div class="summary-item">
                <div class="summary-label">${label}</div>
                <div class="summary-value ${!value ? "empty" : ""}">${
      value || "Non renseigné"
    }</div>
            </div>
        `;
  }

  /**
   * Génération du résumé des documents
   */
  generateDocumentsSummary() {
    let html = "";

    this.documentsRequis.forEach((doc) => {
      const hasFile = this.formData.files.has(doc.type_document);
      const file = this.formData.files.get(doc.type_document);

      html += `
                <div class="document-summary">
                    <div class="document-name">${doc.nom}</div>
                    <div class="document-check ${
                      hasFile ? "success" : "missing"
                    }">
                        ${hasFile ? "✓ Fourni" : "✗ Manquant"}
                        ${file ? ` (${file.name})` : ""}
                    </div>
                </div>
            `;
    });

    return html || "<p>Aucun document requis</p>";
  }

  /**
   * Obtenir le texte d'une option sélectionnée
   */
  getSelectOptionText(selectId) {
    const select = document.getElementById(selectId);
    if (!select || !select.value) return "";

    const option = select.querySelector(`option[value="${select.value}"]`);
    return option ? option.textContent : "";
  }

  /**
   * Formatage d'une date
   */
  formatDate(dateString) {
    if (!dateString) return "";

    try {
      return new Date(dateString).toLocaleDateString("fr-FR");
    } catch {
      return dateString;
    }
  }

  /**
   * Soumission du formulaire
   */
  async handleSubmit(event) {
    event.preventDefault();

    if (this.isSubmitting) {
      console.log("Soumission déjà en cours...");
      return;
    }

    console.log("Début de la soumission de candidature");

    // Validation finale complète
    const validationErrors = this.finalValidation();
    if (validationErrors.length > 0) {
      this.showMessage(
        "error",
        `Erreurs de validation: ${validationErrors.join(", ")}`
      );
      return;
    }

    // Vérifier les conditions obligatoires
    if (!this.checkRequiredConditions()) {
      return;
    }

    try {
      this.isSubmitting = true;
      this.showLoading(true);
      this.disableSubmitButton();

      console.log("Préparation des données pour soumission...");

      // Préparer FormData avec toutes les données
      const formData = this.prepareSubmissionData();

      console.log("Données préparées:", {
        formation: this.formData.formation,
        personal: this.formData.personal,
        filesCount: this.formData.files.size,
      });

      // Soumettre avec headers appropriés
      const response = await fetch("/enrollment/public/candidature/create/", {
        method: "POST",
        body: formData,
        headers: {
          "X-CSRFToken": this.getCSRFToken(),
          "X-Requested-With": "XMLHttpRequest", // Important pour identifier requête AJAX
        },
      });

      console.log("Réponse reçue:", response.status, response.statusText);
      console.log("Content-Type:", response.headers.get("content-type"));

      // Vérifier le content-type de la réponse
      const contentType = response.headers.get("content-type");

      if (response.ok) {
        // Vérifier si la réponse est du JSON
        if (contentType && contentType.includes("application/json")) {
          const result = await response.json();
          console.log("Succès:", result);

          if (result.success) {
            this.showMessage(
              "success",
              "Candidature soumise avec succès ! Redirection en cours..."
            );

            // Supprimer les données sauvegardées
            this.clearSavedData();

            // Redirection vers la page de succès
            setTimeout(() => {
              if (result.redirect_url) {
                window.location.href = result.redirect_url;
              } else {
                // Fallback: construire l'URL manuellement
                const params = new URLSearchParams({
                  numero:
                    result.numero_candidature ||
                    result.candidature_id ||
                    "TEMP",
                  formation: `${this.getSelectOptionText(
                    "filiere"
                  )} - ${this.getSelectOptionText("niveau")}`,
                  etablissement: this.getSelectOptionText("etablissement"),
                });
                window.location.href = `/enrollment/public/candidature/success/?${params.toString()}`;
              }
            }, 2000);
          } else {
            // Erreur côté serveur mais statut 200
            this.showMessage(
              "error",
              result.message || "Erreur lors de la soumission"
            );
            console.error("Erreur serveur:", result);
          }
        } else {
          // Réponse HTML au lieu de JSON - probablement une redirection ou erreur
          const htmlContent = await response.text();
          console.error(
            "Réponse HTML reçue au lieu de JSON:",
            htmlContent.substring(0, 200)
          );

          // Vérifier si c'est une page d'erreur Django
          if (
            htmlContent.includes("<!DOCTYPE") ||
            htmlContent.includes("<html")
          ) {
            this.showMessage(
              "error",
              "Erreur de configuration serveur. La réponse attendue n'a pas été reçue."
            );

            // Essayer d'extraire le message d'erreur de la page HTML
            const errorMatch = htmlContent.match(/<title>(.*?)<\/title>/i);
            if (errorMatch && errorMatch[1].includes("Error")) {
              console.error("Erreur détectée dans le titre:", errorMatch[1]);
            }
          } else {
            this.showMessage("error", "Réponse serveur inattendue");
          }
        }
      } else {
        // Erreur HTTP
        let errorMessage = `Erreur serveur (${response.status})`;

        try {
          if (contentType && contentType.includes("application/json")) {
            const errorData = await response.json();
            errorMessage = errorData.message || errorData.error || errorMessage;

            // Log des erreurs de validation détaillées
            if (errorData.errors || errorData.missing_fields) {
              console.error(
                "Erreurs de validation:",
                errorData.errors || errorData.missing_fields
              );
            }
          } else {
            // Réponse HTML d'erreur
            const htmlError = await response.text();
            console.error("Erreur HTML:", htmlError.substring(0, 500));

            // Essayer d'extraire un message d'erreur utile
            if (htmlError.includes("CSRF")) {
              errorMessage =
                "Erreur de sécurité. Veuillez recharger la page et réessayer.";
            } else if (htmlError.includes("404")) {
              errorMessage = "URL non trouvée. Vérifiez la configuration.";
            } else if (htmlError.includes("500")) {
              errorMessage = "Erreur serveur interne.";
            }
          }
        } catch (parseError) {
          console.error("Erreur parsing réponse d'erreur:", parseError);
        }

        this.showMessage("error", errorMessage);
      }
    } catch (error) {
      console.error("Erreur lors de la soumission:", error);

      let userMessage = "Une erreur de connexion est survenue.";

      if (error.name === "TypeError" && error.message.includes("fetch")) {
        userMessage = "Erreur de connexion. Vérifiez votre connexion internet.";
      } else if (error.name === "AbortError") {
        userMessage = "Requête annulée. Veuillez réessayer.";
      } else if (
        error instanceof SyntaxError &&
        error.message.includes("JSON")
      ) {
        userMessage =
          "Erreur de format de réponse serveur. Contactez le support technique.";
        console.error("Probablement une réponse HTML au lieu de JSON");
      }

      this.showMessage("error", userMessage);
    } finally {
      this.isSubmitting = false;
      this.showLoading(false);
      this.enableSubmitButton();
      console.log("Fin de tentative de soumission");
    }
  }

  /**
   * Vérification des conditions obligatoires
   */
  checkRequiredConditions() {
    const termsCheckbox = document.getElementById("terms");
    const consentCheckbox = document.getElementById("data_consent");

    if (!termsCheckbox?.checked) {
      this.showMessage("error", "Vous devez accepter les conditions générales");
      termsCheckbox?.focus();
      termsCheckbox?.scrollIntoView({ behavior: "smooth", block: "center" });
      return false;
    }

    if (!consentCheckbox?.checked) {
      this.showMessage(
        "error",
        "Vous devez autoriser le traitement de vos données"
      );
      consentCheckbox?.focus();
      consentCheckbox?.scrollIntoView({ behavior: "smooth", block: "center" });
      return false;
    }

    return true;
  }

  /**
   * Préparation des données pour soumission
   */
  prepareSubmissionData() {
    // Sauvegarder les données de l'étape courante
    this.saveCurrentStepData();

    const formData = new FormData();

    // Ajouter toutes les données de formation
    Object.entries(this.formData.formation).forEach(([key, value]) => {
      if (value) {
        formData.append(key, value);
        console.log(`Formation - ${key}: ${value}`);
      }
    });

    // Ajouter toutes les données personnelles
    Object.entries(this.formData.personal).forEach(([key, value]) => {
      if (value) {
        formData.append(key, value);
        console.log(`Personal - ${key}: ${value}`);
      }
    });

    // Ajouter toutes les données académiques
    Object.entries(this.formData.academic).forEach(([key, value]) => {
      if (value) {
        formData.append(key, value);
        console.log(`Academic - ${key}: ${value}`);
      }
    });

    // Ajouter les fichiers avec la bonne nomenclature
    this.formData.files.forEach((file, documentType) => {
      const fieldName = `document_${documentType}`;
      formData.append(fieldName, file, file.name);
      console.log(
        `Document - ${fieldName}: ${file.name} (${this.formatFileSize(
          file.size
        )})`
      );
    });

    // Ajouter les métadonnées
    formData.append(
      "documents_metadata",
      JSON.stringify(
        Array.from(this.formData.files.entries()).map(([type, file]) => ({
          type_document: type,
          nom_fichier: file.name,
          taille: file.size,
          type_mime: file.type,
        }))
      )
    );

    return formData;
  }

  /**
   * Désactivation du bouton de soumission
   */
  disableSubmitButton() {
    const submitBtn = document.getElementById("submit-btn");
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.classList.add("loading");

      const originalText = submitBtn.innerHTML;
      submitBtn.dataset.originalText = originalText;
      submitBtn.innerHTML = `
                <span class="btn-spinner">⟳</span>
                Soumission en cours...
            `;
    }
  }

  /**
   * Réactivation du bouton de soumission
   */
  enableSubmitButton() {
    const submitBtn = document.getElementById("submit-btn");
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.classList.remove("loading");

      if (submitBtn.dataset.originalText) {
        submitBtn.innerHTML = submitBtn.dataset.originalText;
        delete submitBtn.dataset.originalText;
      }
    }
  }

  /**
   * Sauvegarde en brouillon
   */
  async saveDraft() {
    try {
      this.showLoading(true);
      this.saveCurrentStepData();

      // Sauvegarder en local storage
      localStorage.setItem(
        "candidature_draft",
        JSON.stringify({
          formData: {
            formation: this.formData.formation,
            personal: this.formData.personal,
            academic: this.formData.academic,
          },
          currentStep: this.currentStep,
          timestamp: Date.now(),
        })
      );

      this.showMessage("success", "Brouillon sauvegardé localement");
    } catch (error) {
      console.error("Erreur lors de la sauvegarde:", error);
      this.showMessage("error", "Erreur lors de la sauvegarde du brouillon");
    } finally {
      this.showLoading(false);
    }
  }

  /**
   * Chargement des données sauvegardées
   */
  loadSavedData() {
    try {
      const saved = localStorage.getItem("candidature_draft");
      if (!saved) return;

      const data = JSON.parse(saved);
      const age = Date.now() - data.timestamp;

      // Expirer après 24h
      if (age > 24 * 60 * 60 * 1000) {
        localStorage.removeItem("candidature_draft");
        return;
      }

      // Demander à l'utilisateur s'il veut restaurer
      if (
        confirm(
          "Des données de brouillon ont été trouvées. Voulez-vous les restaurer ?"
        )
      ) {
        this.formData.formation = data.formData.formation || {};
        this.formData.personal = data.formData.personal || {};
        this.formData.academic = data.formData.academic || {};

        // Pré-remplir les champs
        this.fillFormFields();

        // Aller à l'étape sauvegardée
        this.currentStep = data.currentStep || 1;
        this.updateStep();

        this.showMessage("info", "Brouillon restauré avec succès");
      }
    } catch (error) {
      console.error("Erreur lors du chargement des données:", error);
      localStorage.removeItem("candidature_draft");
    }
  }

  /**
   * Remplissage des champs du formulaire
   */
  fillFormFields() {
    const allData = {
      ...this.formData.formation,
      ...this.formData.personal,
      ...this.formData.academic,
    };

    Object.keys(allData).forEach((key) => {
      const field =
        document.getElementById(key) ||
        document.querySelector(`[name="${key}"]`);
      if (field && allData[key]) {
        field.value = allData[key];
      }
    });
  }

  /**
   * Suppression des données sauvegardées
   */
  clearSavedData() {
    localStorage.removeItem("candidature_draft");
  }

  /**
   * Vérification des modifications non sauvegardées
   */
  hasUnsavedChanges() {
    // Vérifier s'il y a des données dans le formulaire
    const form = document.getElementById("candidature-form");
    if (!form) return false;

    const inputs = form.querySelectorAll("input, select, textarea");
    for (let input of inputs) {
      if (input.value && input.type !== "file") {
        return true;
      }
    }

    return this.formData.files.size > 0;
  }

  /**
   * Configuration de la persistance des données
   */
  setupFormPersistence() {
    // Sauvegarde automatique toutes les 30 secondes
    setInterval(() => {
      if (this.hasUnsavedChanges()) {
        this.saveDraft();
      }
    }, 30000);
  }

  /**
   * Mise à jour du layout (responsive)
   */
  updateLayout() {
    // Ajustements pour mobile/tablette si nécessaire
    const isMobile = window.innerWidth <= 768;
    const formActions = document.querySelector(".form-actions");

    if (formActions) {
      formActions.classList.toggle("mobile", isMobile);
    }
  }

  /**
   * Affichage du loading
   */
  showLoading(show) {
    const overlay = document.getElementById("loading-overlay");
    if (overlay) {
      overlay.classList.toggle("active", show);
    }
  }

  /**
   * Affichage d'un message
   */
  showMessage(type, message) {
    const container = document.getElementById("message-container");
    if (!container) return;

    // Supprimer les anciens messages après 5 secondes
    const existingMessages = container.querySelectorAll(".message");
    existingMessages.forEach((msg) => {
      setTimeout(() => {
        if (msg.parentNode) {
          msg.remove();
        }
      }, 5000);
    });

    const messageDiv = document.createElement("div");
    messageDiv.className = `message message-${type}`;

    const icon =
      {
        success: "✅",
        error: "❌",
        warning: "⚠️",
        info: "ℹ️",
      }[type] || "ℹ️";

    messageDiv.innerHTML = `
            <span>${icon}</span>
            <span>${message}</span>
            <button type="button" onclick="this.parentNode.remove()" style="margin-left: auto; background: none; border: none; cursor: pointer;">×</button>
        `;

    container.appendChild(messageDiv);

    // Auto-suppression après 5 secondes
    setTimeout(() => {
      if (messageDiv.parentNode) {
        messageDiv.remove();
      }
    }, 5000);

    // Scroll vers le message
    messageDiv.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  /**
   * Récupération du token CSRF
   */
  getCSRFToken() {
    // Méthode 1: Cookie
    const cookieValue = document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="));

    if (cookieValue) {
      return cookieValue.split("=")[1];
    }

    // Méthode 2: Meta tag
    const metaToken = document.querySelector('meta[name="csrf-token"]');
    if (metaToken) {
      return metaToken.getAttribute("content");
    }

    // Méthode 3: Input caché dans un formulaire Django
    const hiddenInput = document.querySelector(
      'input[name="csrfmiddlewaretoken"]'
    );
    if (hiddenInput) {
      return hiddenInput.value;
    }

    console.warn("Token CSRF non trouvé");
    return "";
  }

  /**
   * Formatage de la taille de fichier
   */
  formatFileSize(bytes) {
    if (bytes === 0) return "0 B";

    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  /**
   * Filtrage des documents par niveau
   */
  async filterDocumentsByNiveau(niveauId) {
    try {
      const response = await fetch(
        `/enrollment/api/public/documents_by_niveau/${niveauId}/`
      );

      if (!response.ok) {
        throw new Error(`Erreur HTTP: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        // Mettre à jour la liste des documents si nécessaire
        // Cette méthode peut être utilisée pour affiner la liste selon le niveau
        console.log("Documents filtrés par niveau:", data.data);
      }
    } catch (error) {
      console.error("Erreur lors du filtrage par niveau:", error);
    }
  }

  /**
   * Fonction utilitaire de debounce
   */
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  /**
   * Gestion des erreurs globales
   */
  handleGlobalError(error) {
    console.error("Erreur globale:", error);
    this.showMessage(
      "error",
      "Une erreur inattendue s'est produite. Veuillez recharger la page."
    );
  }

  /**
   * Validation finale avant soumission
   */
  finalValidation() {
    const errors = [];

    // Vérifier les données de formation
    const requiredFormation = {
      etablissement: "Établissement",
      departement: "Département",
      filiere: "Filière",
      niveau: "Niveau",
      annee_academique: "Année académique",
    };

    Object.entries(requiredFormation).forEach(([field, label]) => {
      if (!this.formData.formation[field]) {
        errors.push(`${label} est requis`);
      }
    });

    // Vérifier les données personnelles obligatoires
    const requiredPersonal = {
      prenom: "Prénom",
      nom: "Nom",
      date_naissance: "Date de naissance",
      lieu_naissance: "Lieu de naissance",
      genre: "Genre",
      telephone: "Téléphone",
      email: "Email",
      adresse: "Adresse",
    };

    Object.entries(requiredPersonal).forEach(([field, label]) => {
      if (!this.formData.personal[field]) {
        errors.push(`${label} est requis`);
      }
    });

    // Validation de l'email
    if (this.formData.personal.email) {
      const emailError = this.validators.email(this.formData.personal.email);
      if (emailError) {
        errors.push(emailError);
      }
    }

    // Validation du téléphone
    if (this.formData.personal.telephone) {
      const phoneError = this.validators.telephone(
        this.formData.personal.telephone
      );
      if (phoneError) {
        errors.push(phoneError);
      }
    }

    // Vérifier les documents obligatoires
    const missingDocs = this.getMissingRequiredDocuments();
    if (missingDocs.length > 0) {
      errors.push(
        `Documents obligatoires manquants: ${missingDocs.join(", ")}`
      );
    }

    // Vérifier la taille totale des fichiers (limiter à 50MB total)
    const totalSize = Array.from(this.formData.files.values()).reduce(
      (total, file) => total + file.size,
      0
    );

    if (totalSize > 50 * 1024 * 1024) {
      errors.push("La taille totale des fichiers ne doit pas dépasser 50MB");
    }

    return errors;
  }

  /**
   * Méthode de debug pour analyser les réponses problématiques
   */
  async debugResponse(response) {
    const responseClone = response.clone();
    const contentType = response.headers.get("content-type");

    console.log("=== DEBUG RESPONSE ===");
    console.log("Status:", response.status);
    console.log("StatusText:", response.statusText);
    console.log("Content-Type:", contentType);
    console.log("Headers:", [...response.headers.entries()]);

    if (contentType && contentType.includes("text/html")) {
      const htmlContent = await responseClone.text();
      console.log(
        "HTML Content (first 500 chars):",
        htmlContent.substring(0, 500)
      );

      // Chercher des indices d'erreur dans le HTML
      if (htmlContent.includes("CSRF verification failed")) {
        console.log("PROBLÈME: Erreur CSRF détectée");
      }
      if (htmlContent.includes("404")) {
        console.log("PROBLÈME: Page non trouvée (404)");
      }
      if (
        htmlContent.includes("500") ||
        htmlContent.includes("Internal Server Error")
      ) {
        console.log("PROBLÈME: Erreur serveur interne (500)");
      }
    }
    console.log("=== END DEBUG ===");
  }

  /**
   * Amélioration de la gestion des erreurs réseau
   */
  handleNetworkError(error) {
    let message = "Erreur de connexion";
    let technicalDetails = error.toString();

    if (!navigator.onLine) {
      message =
        "Vous semblez être hors ligne. Vérifiez votre connexion internet.";
    } else if (error.name === "TypeError") {
      if (error.message.includes("fetch")) {
        message =
          "Impossible de contacter le serveur. Vérifiez l'URL et votre connexion.";
      } else if (error.message.includes("JSON")) {
        message =
          "Erreur de format de données. Le serveur a renvoyé une réponse inattendue.";
        technicalDetails += "\n(Probablement une page HTML au lieu de JSON)";
      }
    } else if (error.code === "NETWORK_ERROR") {
      message = "Erreur réseau. Vérifiez votre connexion.";
    }

    this.showMessage("error", message);
    console.error("Erreur réseau détaillée:", technicalDetails);

    // Afficher plus de détails en mode debug
    if (
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1"
    ) {
      console.error("DÉTAILS TECHNIQUES (dev only):", error);
    }
  }

  /**
   * Retry automatique en cas d'échec
   */
  async submitWithRetry(formData, maxRetries = 3) {
    let lastError;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        console.log(`Tentative ${attempt}/${maxRetries}`);

        if (attempt > 1) {
          // Attendre avant retry
          await new Promise((resolve) => setTimeout(resolve, 1000 * attempt));
          this.showMessage(
            "info",
            `Nouvelle tentative (${attempt}/${maxRetries})...`
          );
        }

        const response = await fetch("/enrollment/public/candidature/create/", {
          method: "POST",
          body: formData,
          headers: {
            "X-CSRFToken": this.getCSRFToken(),
          },
        });

        // Si succès, retourner la réponse
        if (response.ok || response.status < 500) {
          return response;
        }

        throw new Error(`Erreur serveur: ${response.status}`);
      } catch (error) {
        lastError = error;
        console.warn(`Tentative ${attempt} échouée:`, error.message);

        // Si c'est la dernière tentative ou une erreur non-retry-able, throw
        if (attempt === maxRetries || error.status < 500) {
          throw error;
        }
      }
    }

    throw lastError;
  }

  /**
   * Nettoyage lors de la destruction
   */
  destroy() {
    // Supprimer les event listeners
    window.removeEventListener("beforeunload", this.beforeUnloadHandler);
    window.removeEventListener("resize", this.resizeHandler);

    // Nettoyer les données
    this.clearSavedData();

    console.log("Formulaire de candidature détruit");
  }
}

// Styles CSS pour les éléments créés dynamiquement
const dynamicStyles = `
<style>
.preview-modal {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
}

.preview-content {
    background: white;
    border-radius: 12px;
    max-width: 90vw;
    max-height: 90vh;
    overflow: hidden;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}

.preview-header {
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #e5e5e5;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #f8f9fa;
}

.preview-header h3 {
    margin: 0;
    color: #1e3a5f;
    font-weight: 600;
}

.close-btn {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0.5rem;
    border-radius: 6px;
    transition: background-color 0.2s;
}

.close-btn:hover {
    background: rgba(0,0,0,0.1);
}

.preview-body {
    padding: 1.5rem;
    text-align: center;
    max-height: 70vh;
    overflow: auto;
}

.form-actions.mobile {
    flex-direction: column;
    gap: 1rem;
}

.form-actions.mobile .actions-right {
    order: -1;
    width: 100%;
    justify-content: space-between;
}

.form-actions.mobile .btn {
    flex: 1;
    min-width: 0;
}

@media (max-width: 480px) {
    .preview-content {
        margin: 1rem;
        max-width: calc(100vw - 2rem);
        max-height: calc(100vh - 2rem);
    }
    
    .preview-header {
        padding: 1rem;
    }
    
    .preview-body {
        padding: 1rem;
    }
}
</style>
`;

// Injection des styles dynamiques
document.head.insertAdjacentHTML("beforeend", dynamicStyles);

// Initialisation globale
let candidatureForm;

// Initialisation lors du chargement de la page
document.addEventListener("DOMContentLoaded", function () {
  console.log("DOM chargé, initialisation du formulaire...");

  try {
    candidatureForm = new CandidatureForm();
    window.candidatureForm = candidatureForm; // Rendre accessible globalement
    console.log("Formulaire initialisé avec succès");
  } catch (error) {
    console.error("Erreur lors de l'initialisation:", error);

    // Afficher un message d'erreur à l'utilisateur
    const container = document.getElementById("message-container");
    if (container) {
      container.innerHTML = `
                <div class="message message-error">
                    <span>❌</span>
                    <span>Erreur d'initialisation du formulaire. Veuillez recharger la page.</span>
                </div>
            `;
    }
  }
});

// Gestion des erreurs globales JavaScript
window.addEventListener("error", function (event) {
  console.error("Erreur JavaScript globale:", event.error);

  if (window.candidatureForm) {
    window.candidatureForm.handleGlobalError(event.error);
  }
});

// Gestion des promesses rejetées non catchées
window.addEventListener("unhandledrejection", function (event) {
  console.error("Promise rejetée non gérée:", event.reason);

  if (window.candidatureForm) {
    window.candidatureForm.handleGlobalError(event.reason);
  }

  // Empêcher l'affichage de l'erreur dans la console
  event.preventDefault();
});

// Fonctions utilitaires globales (accessibles depuis le HTML)
window.candidatureFormUtils = {
  /**
   * Redirection vers une URL
   */
  redirectTo(url) {
    window.location.href = url;
  },

  /**
   * Confirmation de navigation
   */
  confirmNavigation(
    message = "Êtes-vous sûr de vouloir quitter ? Les modifications non sauvegardées seront perdues."
  ) {
    if (candidatureForm && candidatureForm.hasUnsavedChanges()) {
      return confirm(message);
    }
    return true;
  },

  /**
   * Sauvegarde manuelle
   */
  saveManually() {
    if (candidatureForm) {
      candidatureForm.saveDraft();
    }
  },

  /**
   * Reset du formulaire
   */
  resetForm() {
    if (
      confirm(
        "Êtes-vous sûr de vouloir réinitialiser le formulaire ? Toutes les données seront perdues."
      )
    ) {
      candidatureForm.clearSavedData();
      window.location.reload();
    }
  },
};

// Export pour utilisation en module (si nécessaire)
if (typeof module !== "undefined" && module.exports) {
  module.exports = CandidatureForm;
}
