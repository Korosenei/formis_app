/**
 * candidature.js - Gestionnaire de formulaire de candidature académique
 * Version: 1.0.0
 * Compatible avec Django et l'architecture définie
 */

"use strict";

/**
 * Gestionnaire principal du formulaire de candidature
 */
class CandidatureFormManager {
  constructor() {
    this.currentStep = 1;
    this.maxStep = 4;
    this.formData = new Map();
    this.documentsRequired = [];
    this.documentsUploaded = [];
    this.validationErrors = new Map();
    this.isSubmitting = false;

    // État de la sélection en cascade
    this.selectionState = {
      etablissement: null,
      departement: null,
      filiere: null,
      niveau: null,
      anneeAcademique: null,
    };

    // Configuration
    this.config = {
      apiEndpoints: {
        etablissements: "/establishments/api/public/etablissements/",
        departements: "/academic/api/public/departements/",
        filieres: "/academic/api/public/filieres/",
        niveaux: "/academic/api/public/niveaux/",
        documents: "/enrollment/api/public/documents_by_filiere/",
        submit: "/enrollment/candidatures/create/",
      },
      validation: {
        minAge: 15,
        maxAge: 100,
        phonePattern: /^(\+226|00226|226)?[0-9\s]{8,}$/,
        emailPattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
      },
      files: {
        maxSize: 5242880, // 5MB
        allowedTypes: ["pdf", "jpg", "jpeg", "png", "doc", "docx"],
        mimeTypes: {
          pdf: "application/pdf",
          jpg: "image/jpeg",
          jpeg: "image/jpeg",
          png: "image/png",
          doc: "application/msword",
          docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
      },
      autoSave: {
        interval: 30000, // 30 secondes
        key: "candidature_draft",
      },
    };

    this.init();
  }

  /**
   * Initialisation du gestionnaire
   */
  init() {
    this.bindEvents();
    this.loadInitialData();
    this.setupAutoSave();
    this.showStep(1);
    this.updateProgressBar();

    console.log("[CandidatureForm] Initialisé");
  }

  /**
   * Liaison des événements
   */
  bindEvents() {
    // Navigation
    this.bindNavigationEvents();

    // Validation temps réel
    this.bindValidationEvents();

    // Événements spécifiques par étape
    this.bindStep1Events();
    this.bindStep2Events();
    this.bindStep4Events();
  }

  /**
   * Événements de navigation
   */
  bindNavigationEvents() {
    const nextBtn = document.getElementById("next-step");
    const prevBtn = document.getElementById("prev-step");
    const submitBtn = document.getElementById("submit-form");

    if (nextBtn) {
      nextBtn.addEventListener("click", () => this.nextStep());
    }

    if (prevBtn) {
      prevBtn.addEventListener("click", () => this.prevStep());
    }

    if (submitBtn) {
      submitBtn.addEventListener("click", (e) => this.submitForm(e));
    }
  }

  /**
   * Événements de validation
   */
  bindValidationEvents() {
    const form = document.getElementById("candidature-form");
    if (!form) return;

    const inputs = form.querySelectorAll("input, select, textarea");
    inputs.forEach((input) => {
      // Validation sur perte de focus
      input.addEventListener("blur", () => {
        this.validateField(input);
        this.saveFormData();
      });

      // Nettoyer les erreurs pendant la saisie
      input.addEventListener("input", () => {
        this.clearFieldError(input);
      });

      // Sauvegarde sur changement
      input.addEventListener("change", () => {
        this.saveFormData();
      });
    });
  }

  /**
   * Événements étape 1 - Informations personnelles
   */
  bindStep1Events() {
    // Formatage téléphone
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    phoneInputs.forEach((input) => {
      input.addEventListener("input", this.formatPhoneNumber.bind(this));
    });

    // Validation âge
    const dateNaissance = document.getElementById("date_naissance");
    if (dateNaissance) {
      dateNaissance.addEventListener("change", this.validateAge.bind(this));
    }

    // Mise à jour résumé temps réel
    const step1Fields = document.querySelectorAll(
      "#step-1 input, #step-1 select, #step-1 textarea"
    );
    step1Fields.forEach((field) => {
      field.addEventListener("input", this.updateStep1Summary.bind(this));
    });
  }

  /**
   * Événements étape 2 - Choix formation
   */
  bindStep2Events() {
    const etablissementSelect = document.getElementById("etablissement");
    const departementSelect = document.getElementById("departement");
    const filiereSelect = document.getElementById("filiere");
    const niveauSelect = document.getElementById("niveau");
    const anneeSelect = document.getElementById("annee_academique");

    if (etablissementSelect) {
      etablissementSelect.addEventListener("change", (e) => {
        this.handleEtablissementChange(e.target.value);
      });
    }

    if (departementSelect) {
      departementSelect.addEventListener("change", (e) => {
        this.handleDepartementChange(e.target.value);
      });
    }

    if (filiereSelect) {
      filiereSelect.addEventListener("change", (e) => {
        this.handleFiliereChange(e.target.value);
      });
    }

    if (niveauSelect) {
      niveauSelect.addEventListener("change", (e) => {
        this.handleNiveauChange(e.target.value);
      });
    }

    if (anneeSelect) {
      anneeSelect.addEventListener("change", (e) => {
        this.handleAnneeChange(e.target.value);
      });
    }
  }

  /**
   * Événements étape 4 - Récapitulatif
   */
  bindStep4Events() {
    const termsCheckbox = document.getElementById("accept_terms");
    if (termsCheckbox) {
      termsCheckbox.addEventListener(
        "change",
        this.updateSubmissionStatus.bind(this)
      );
    }
  }

  /**
   * Chargement des données initiales
   */
  async loadInitialData() {
    try {
      this.showNotification("Chargement...", "info");

      await this.loadEtablissements();
      this.loadSavedFormData();

      this.showNotification("Formulaire prêt", "success", 2000);
    } catch (error) {
      console.error("[CandidatureForm] Erreur chargement initial:", error);
      this.showNotification("Erreur de chargement", "error");
    }
  }

  /**
   * Chargement des établissements
   */
  async loadEtablissements() {
    try {
      const response = await this.makeAPIRequest(
        this.config.apiEndpoints.etablissements
      );

      if (response.success && response.data) {
        const select = document.getElementById("etablissement");
        if (select) {
          this.populateSelect(
            select,
            response.data,
            "Choisissez un établissement"
          );
        }
      } else {
        throw new Error("Erreur chargement établissements");
      }
    } catch (error) {
      console.warn(
        "[CandidatureForm] API indisponible, utilisation données fallback"
      );
      this.loadFallbackEtablissements();
    }
  }

  /**
   * Données de fallback pour établissements
   */
  loadFallbackEtablissements() {
    const etablissements = [
      { id: "1", nom: "Université de Ouagadougou", code: "UO" },
      { id: "2", nom: "École Supérieure de Commerce", code: "ESC" },
      { id: "3", nom: "Institut Polytechnique", code: "IPO" },
      { id: "4", nom: "École Nationale de Santé", code: "ENSP" },
    ];

    const select = document.getElementById("etablissement");
    if (select) {
      this.populateSelect(
        select,
        etablissements,
        "Choisissez un établissement"
      );
    }
  }

  /**
   * Gestion sélection établissement
   */
  async handleEtablissementChange(etablissementId) {
    if (!etablissementId) {
      this.resetSelectionFrom("departement");
      return;
    }

    const select = document.getElementById("etablissement");
    const selectedOption = select.options[select.selectedIndex];

    this.selectionState.etablissement = {
      id: etablissementId,
      nom: selectedOption.text,
      code: selectedOption.dataset.code || "XX",
    };

    await this.loadDepartements(etablissementId);
    this.resetSelectionFrom("departement");
  }

  /**
   * Chargement départements
   */
  async loadDepartements(etablissementId) {
    const select = document.getElementById("departement");
    if (!select) return;

    this.showSelectLoading(select, "Chargement départements...");

    try {
      const url = `${this.config.apiEndpoints.departements}${etablissementId}/`;
      const response = await this.makeAPIRequest(url);

      if (response.success && response.data) {
        this.populateSelect(select, response.data, "Choisissez un département");
        this.showElement("departement-group");
      } else {
        throw new Error("Erreur chargement départements");
      }
    } catch (error) {
      console.warn("[CandidatureForm] Fallback départements");
      const departements = [
        { id: "1", nom: "Sciences Informatiques", code: "SI" },
        { id: "2", nom: "Sciences Économiques", code: "SE" },
        { id: "3", nom: "Lettres et Sciences Humaines", code: "LSH" },
      ];
      this.populateSelect(select, departements, "Choisissez un département");
      this.showElement("departement-group");
    }
  }

  /**
   * Gestion sélection département
   */
  async handleDepartementChange(departementId) {
    if (!departementId) {
      this.resetSelectionFrom("filiere");
      return;
    }

    const select = document.getElementById("departement");
    const selectedOption = select.options[select.selectedIndex];

    this.selectionState.departement = {
      id: departementId,
      nom: selectedOption.text,
      code: selectedOption.dataset.code || "XX",
    };

    await this.loadFilieres(departementId);
    this.resetSelectionFrom("filiere");
  }

  /**
   * Chargement filières
   */
  async loadFilieres(departementId) {
    const select = document.getElementById("filiere");
    if (!select) return;

    this.showSelectLoading(select, "Chargement filières...");

    try {
      const url = `${this.config.apiEndpoints.filieres}${departementId}/`;
      const response = await this.makeAPIRequest(url);

      if (response.success && response.data) {
        this.populateSelect(select, response.data, "Choisissez une filière");
        this.showElement("filiere-group");
      } else {
        throw new Error("Erreur chargement filières");
      }
    } catch (error) {
      console.warn("[CandidatureForm] Fallback filières");
      const filieres = [
        { id: "1", nom: "Licence Informatique", code: "LI", duree: "3 ans" },
        { id: "2", nom: "Master Informatique", code: "MI", duree: "2 ans" },
        { id: "3", nom: "Licence Économie", code: "LE", duree: "3 ans" },
      ];
      this.populateSelect(select, filieres, "Choisissez une filière");
      this.showElement("filiere-group");
    }
  }

  /**
   * Gestion sélection filière
   */
  async handleFiliereChange(filiereId) {
    if (!filiereId) {
      this.resetSelectionFrom("niveau");
      return;
    }

    const select = document.getElementById("filiere");
    const selectedOption = select.options[select.selectedIndex];

    this.selectionState.filiere = {
      id: filiereId,
      nom: selectedOption.text,
      code: selectedOption.dataset.code || "XX",
      duree: selectedOption.dataset.duree || "3 ans",
    };

    await this.loadNiveaux(filiereId);
    this.loadAnneesAcademiques();
    this.resetSelectionFrom("niveau");
  }

  /**
   * Chargement niveaux
   */
  async loadNiveaux(filiereId) {
    const select = document.getElementById("niveau");
    if (!select) return;

    this.showSelectLoading(select, "Chargement niveaux...");

    try {
      const url = `${this.config.apiEndpoints.niveaux}${filiereId}/`;
      const response = await this.makeAPIRequest(url);

      if (response.success && response.data) {
        this.populateSelect(select, response.data, "Choisissez un niveau");
        this.showElement("niveau-group");
      } else {
        throw new Error("Erreur chargement niveaux");
      }
    } catch (error) {
      console.warn("[CandidatureForm] Fallback niveaux");
      const niveaux = [
        { id: "1", nom: "Première année (L1)", code: "L1" },
        { id: "2", nom: "Deuxième année (L2)", code: "L2" },
        { id: "3", nom: "Troisième année (L3)", code: "L3" },
      ];
      this.populateSelect(select, niveaux, "Choisissez un niveau");
      this.showElement("niveau-group");
    }
  }

  /**
   * Gestion sélection niveau
   */
  handleNiveauChange(niveauId) {
    if (!niveauId) {
      this.selectionState.niveau = null;
      this.hideElement("selection-summary");
      return;
    }

    const select = document.getElementById("niveau");
    const selectedOption = select.options[select.selectedIndex];

    this.selectionState.niveau = {
      id: niveauId,
      nom: selectedOption.text,
      code: selectedOption.dataset.code || "XX",
    };

    this.updateSelectionSummary();
  }

  /**
   * Chargement années académiques
   */
  loadAnneesAcademiques() {
    const select = document.getElementById("annee_academique");
    if (!select) return;

    const currentYear = new Date().getFullYear();
    const annees = [];

    for (let i = 0; i < 3; i++) {
      const startYear = currentYear + i;
      const endYear = startYear + 1;
      annees.push({
        id: `${startYear}-${endYear}`,
        nom: `${startYear}-${endYear}`,
        code: `${startYear}-${endYear}`,
      });
    }

    this.populateSelect(select, annees, "Choisissez l'année académique");
    this.showElement("annee-academique-group");
  }

  /**
   * Gestion sélection année
   */
  handleAnneeChange(anneeValue) {
    if (!anneeValue) {
      this.selectionState.anneeAcademique = null;
      return;
    }

    this.selectionState.anneeAcademique = {
      periode: anneeValue,
      nom: anneeValue,
    };

    this.updateSelectionSummary();
  }

  /**
   * Mise à jour résumé sélection
   */
  updateSelectionSummary() {
    const { etablissement, departement, filiere, niveau, anneeAcademique } =
      this.selectionState;

    if (!etablissement || !departement || !filiere || !niveau) {
      this.hideElement("selection-summary");
      return;
    }

    this.updateElementText("summary-etablissement", etablissement.nom);
    this.updateElementText("summary-departement", departement.nom);
    this.updateElementText("summary-filiere", filiere.nom);
    this.updateElementText("summary-niveau", niveau.nom);
    this.updateElementText(
      "summary-annee",
      anneeAcademique ? anneeAcademique.nom : "À sélectionner"
    );

    this.showElement("selection-summary");
  }

  /**
   * Chargement documents requis
   */
  async loadDocumentsRequired() {
    const filiereId = this.selectionState.filiere?.id;
    if (!filiereId) {
      this.showNotification("Sélectionnez d'abord une filière", "warning");
      return;
    }

    this.showDocumentsLoading();

    try {
      const url = `${this.config.apiEndpoints.documents}${filiereId}/`;
      const response = await this.makeAPIRequest(url);

      if (response.success && response.data) {
        this.documentsRequired = response.data.documents_requis || [];
        this.renderDocumentsList();
        this.updateDocumentsSummary();
      } else {
        throw new Error("Erreur chargement documents");
      }
    } catch (error) {
      console.warn("[CandidatureForm] Fallback documents");
      this.loadFallbackDocuments();
    }
  }

  /**
   * Documents de fallback
   */
  loadFallbackDocuments() {
    this.documentsRequired = [
      {
        id: 1,
        nom: "Pièce d'identité",
        description: "Carte nationale d'identité ou passeport",
        type_document: "PIECE_IDENTITE",
        est_obligatoire: true,
        taille_maximale: this.config.files.maxSize,
        formats_autorises: ["pdf", "jpg", "jpeg", "png"],
      },
      {
        id: 2,
        nom: "Acte de naissance",
        description: "Acte de naissance certifié conforme",
        type_document: "ACTE_NAISSANCE",
        est_obligatoire: true,
        taille_maximale: this.config.files.maxSize,
        formats_autorises: ["pdf", "jpg", "jpeg", "png"],
      },
      {
        id: 3,
        nom: "Dernier diplôme",
        description: "Copie certifiée du dernier diplôme obtenu",
        type_document: "DIPLOME",
        est_obligatoire: true,
        taille_maximale: this.config.files.maxSize,
        formats_autorises: ["pdf", "jpg", "jpeg", "png"],
      },
      {
        id: 4,
        nom: "Photo d'identité",
        description: "Photo d'identité récente format 4x4",
        type_document: "PHOTO_IDENTITE",
        est_obligatoire: false,
        taille_maximale: 2097152,
        formats_autorises: ["jpg", "jpeg", "png"],
      },
    ];

    this.renderDocumentsList();
    this.updateDocumentsSummary();
  }

  /**
   * Rendu liste documents
   */
  renderDocumentsList() {
    const container = document.getElementById("documents-container");
    if (!container) return;

    container.innerHTML = "";

    const listDiv = document.createElement("div");
    listDiv.className = "documents-list";
    listDiv.id = "documents-list";

    this.documentsRequired.forEach((doc, index) => {
      const docElement = this.createDocumentElement(doc, index);
      listDiv.appendChild(docElement);
    });

    container.appendChild(listDiv);
    this.bindDocumentEvents();
    this.hideDocumentsLoading();
    this.showElement("documents-summary");
  }

  /**
   * Création élément document
   */
  createDocumentElement(doc, index) {
    const docDiv = document.createElement("div");
    docDiv.className = `document-item ${
      doc.est_obligatoire ? "required" : "optional"
    }`;
    docDiv.setAttribute("data-type", doc.type_document);
    docDiv.setAttribute("data-index", index);

    const uploaded = this.documentsUploaded.find(
      (d) => d.type_document === doc.type_document
    );

    docDiv.innerHTML = `
            <div class="document-header">
                <div class="document-info">
                    <h4>${doc.nom}</h4>
                    <p>${doc.description || "Aucune description disponible"}</p>
                    <div class="document-meta">
                        <span>Formats: ${doc.formats_autorises
                          .join(", ")
                          .toUpperCase()}</span>
                        <span>Taille max: ${this.formatFileSize(
                          doc.taille_maximale
                        )}</span>
                    </div>
                </div>
                <div class="document-status">
                    <span class="status-badge ${
                      uploaded
                        ? "completed"
                        : doc.est_obligatoire
                        ? "required"
                        : "optional"
                    }">
                        ${
                          uploaded
                            ? "Téléchargé"
                            : doc.est_obligatoire
                            ? "Requis"
                            : "Optionnel"
                        }
                    </span>
                </div>
            </div>
            <div class="document-content">
                ${
                  uploaded
                    ? this.createFilePreview(uploaded)
                    : this.createUploadZone(doc, index)
                }
            </div>
        `;

    if (uploaded) {
      docDiv.classList.add("completed");
    }

    return docDiv;
  }

  /**
   * Création zone upload
   */
  createUploadZone(doc, index) {
    return `
            <div class="document-upload">
                <input type="file" 
                       id="file-${index}" 
                       class="file-input"
                       accept="${this.getAcceptTypes(doc.formats_autorises)}"
                       data-max-size="${doc.taille_maximale}"
                       data-doc-type="${doc.type_document}">
                <div class="upload-zone" data-type="${doc.type_document}">
                    <div class="upload-icon">📁</div>
                    <div class="upload-text">
                        <span class="upload-main">Cliquez ou glissez le fichier ici</span>
                        <span class="upload-hint">Formats: ${doc.formats_autorises
                          .join(", ")
                          .toUpperCase()}</span>
                    </div>
                </div>
            </div>
        `;
  }

  /**
   * Création aperçu fichier
   */
  createFilePreview(docData) {
    return `
            <div class="file-preview">
                <div class="file-info">
                    <div class="file-icon">${this.getFileIcon(
                      docData.format_fichier
                    )}</div>
                    <div class="file-details">
                        <div class="file-name">${docData.nom}</div>
                        <div class="file-size">${this.formatFileSize(
                          docData.taille_fichier
                        )}</div>
                        <div class="file-upload-date">Téléchargé le ${docData.upload_date.toLocaleDateString(
                          "fr-FR"
                        )}</div>
                    </div>
                </div>
                <div class="file-actions">
                    <button type="button" class="btn-icon btn-view" title="Aperçu" data-doc-type="${
                      docData.type_document
                    }">👁️</button>
                    <button type="button" class="btn-icon btn-replace" title="Remplacer" data-doc-type="${
                      docData.type_document
                    }">🔄</button>
                    <button type="button" class="btn-icon btn-delete" title="Supprimer" data-doc-type="${
                      docData.type_document
                    }">🗑️</button>
                </div>
            </div>
        `;
  }

  /**
   * Liaison événements documents
   */
  bindDocumentEvents() {
    // Upload fichiers
    document.querySelectorAll(".file-input").forEach((input) => {
      input.addEventListener("change", this.handleFileSelect.bind(this));
    });

    // Zones drag & drop
    document.querySelectorAll(".upload-zone").forEach((zone) => {
      zone.addEventListener("click", this.handleUploadClick.bind(this));
      zone.addEventListener("dragover", this.handleDragOver.bind(this));
      zone.addEventListener("dragleave", this.handleDragLeave.bind(this));
      zone.addEventListener("drop", this.handleFileDrop.bind(this));
    });

    // Actions fichiers
    document.querySelectorAll(".btn-view").forEach((btn) => {
      btn.addEventListener("click", (e) =>
        this.viewFile(e.target.dataset.docType)
      );
    });

    document.querySelectorAll(".btn-replace").forEach((btn) => {
      btn.addEventListener("click", (e) =>
        this.replaceFile(e.target.dataset.docType)
      );
    });

    document.querySelectorAll(".btn-delete").forEach((btn) => {
      btn.addEventListener("click", (e) =>
        this.deleteFile(e.target.dataset.docType)
      );
    });
  }

  /**
   * Gestion sélection fichier
   */
  handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const docType = event.target.getAttribute("data-doc-type");
    const maxSize = parseInt(event.target.getAttribute("data-max-size"));

    if (this.validateFile(file, maxSize)) {
      this.addDocument(file, docType);
    } else {
      event.target.value = "";
    }
  }

  /**
   * Gestion clic zone upload
   */
  handleUploadClick(event) {
    const input =
      event.currentTarget.parentElement.querySelector(".file-input");
    if (input) {
      input.click();
    }
  }

  /**
   * Gestion drag over
   */
  handleDragOver(event) {
    event.preventDefault();
    event.currentTarget.classList.add("dragover");
  }

  /**
   * Gestion drag leave
   */
  handleDragLeave(event) {
    event.currentTarget.classList.remove("dragover");
  }

  /**
   * Gestion drop fichier
   */
  handleFileDrop(event) {
    event.preventDefault();
    event.currentTarget.classList.remove("dragover");

    const files = event.dataTransfer.files;
    if (files.length > 0) {
      const docType = event.currentTarget.dataset.type;
      const docRequired = this.documentsRequired.find(
        (d) => d.type_document === docType
      );

      if (
        docRequired &&
        this.validateFile(files[0], docRequired.taille_maximale)
      ) {
        this.addDocument(files[0], docType);
      }
    }
  }

  /**
   * Validation fichier
   */
  validateFile(file, maxSize) {
    if (file.size > maxSize) {
      this.showNotification(
        `Fichier trop volumineux (max ${this.formatFileSize(maxSize)})`,
        "error"
      );
      return false;
    }

    const extension = file.name.split(".").pop().toLowerCase();
    if (!this.config.files.allowedTypes.includes(extension)) {
      this.showNotification(
        `Format non autorisé. Formats acceptés: ${this.config.files.allowedTypes.join(
          ", "
        )}`,
        "error"
      );
      return false;
    }

    return true;
  }

  /**
   * Ajout document
   */
  addDocument(file, docType) {
    const docData = {
      type_document: docType,
      nom: file.name,
      taille_fichier: file.size,
      format_fichier: file.name.split(".").pop().toLowerCase(),
      file: file,
      upload_date: new Date(),
    };

    const existingIndex = this.documentsUploaded.findIndex(
      (doc) => doc.type_document === docType
    );
    if (existingIndex !== -1) {
      this.documentsUploaded[existingIndex] = docData;
    } else {
      this.documentsUploaded.push(docData);
    }

    this.renderDocumentsList();
    this.updateDocumentsSummary();
    this.showNotification("Document téléchargé avec succès", "success");
  }

  /**
   * Actions fichiers
   */
  viewFile(docType) {
    const doc = this.documentsUploaded.find((d) => d.type_document === docType);
    if (doc && doc.file) {
      const url = URL.createObjectURL(doc.file);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  }

  replaceFile(docType) {
    const docElement = document.querySelector(`[data-type="${docType}"]`);
    const input = docElement.querySelector(".file-input");
    if (input) {
      input.click();
    }
  }

  deleteFile(docType) {
    if (confirm("Êtes-vous sûr de vouloir supprimer ce document ?")) {
      this.documentsUploaded = this.documentsUploaded.filter(
        (doc) => doc.type_document !== docType
      );
      this.renderDocumentsList();
      this.updateDocumentsSummary();
      this.showNotification("Document supprimé", "info");
    }
  }

  /**
   * Mise à jour du résumé des documents
   */
  updateDocumentsSummary() {
    const requiredDocs = this.documentsRequired.filter(
      (doc) => doc.est_obligatoire
    );
    const optionalDocs = this.documentsRequired.filter(
      (doc) => !doc.est_obligatoire
    );
    const uploadedTypes = this.documentsUploaded.map(
      (doc) => doc.type_document
    );
    const missingRequired = requiredDocs.filter(
      (doc) => !uploadedTypes.includes(doc.type_document)
    );

    // Mise à jour des compteurs
    this.updateElementText("docs-required-count", requiredDocs.length);
    this.updateElementText(
      "docs-uploaded-count",
      this.documentsUploaded.length
    );
    this.updateElementText("docs-missing-count", missingRequired.length);
    this.updateElementText("docs-optional-count", optionalDocs.length);

    // Calcul et affichage de la progression
    const progress =
      requiredDocs.length > 0
        ? ((requiredDocs.length - missingRequired.length) /
            requiredDocs.length) *
          100
        : 100;

    this.updateElementText("progress-percentage", `${Math.round(progress)}%`);
    const progressBar = document.getElementById("progress-bar-fill");
    if (progressBar) {
      progressBar.style.width = `${progress}%`;
    }

    // Messages de validation
    const validationMessage = document.getElementById("validation-message");
    const missingDocuments = document.getElementById("missing-documents");

    if (missingRequired.length === 0) {
      this.showElement("validation-message");
      this.hideElement("missing-documents");
    } else {
      this.hideElement("validation-message");
      this.showElement("missing-documents");

      const missingList = document.getElementById("missing-documents-list");
      if (missingList) {
        missingList.innerHTML = missingRequired
          .map((doc) => `<li>${doc.nom}</li>`)
          .join("");
      }
    }
  }

  /**
   * Navigation entre les étapes
   */
  nextStep() {
    if (this.currentStep >= this.maxStep) return;

    if (this.validateCurrentStep()) {
      // Actions spéciales selon l'étape
      if (this.currentStep === 2) {
        this.loadDocumentsRequired();
      } else if (this.currentStep === 3) {
        this.generateRecapitulatif();
      }

      this.currentStep++;
      this.showStep(this.currentStep);
      this.updateProgressBar();
      this.scrollToTop();
    }
  }

  prevStep() {
    if (this.currentStep <= 1) return;

    this.currentStep--;
    this.showStep(this.currentStep);
    this.updateProgressBar();
    this.scrollToTop();
  }

  /**
   * Affichage d'une étape
   */
  showStep(stepNumber) {
    // Masquer toutes les étapes
    document.querySelectorAll(".form-step").forEach((step) => {
      step.classList.remove("active");
    });

    // Afficher l'étape demandée
    const targetStep = document.getElementById(`step-${stepNumber}`);
    if (targetStep) {
      targetStep.classList.add("active");
    }

    // Mettre à jour les boutons de navigation
    this.updateNavigationButtons();
  }

  /**
   * Mise à jour des boutons de navigation
   */
  updateNavigationButtons() {
    const prevBtn = document.getElementById("prev-step");
    const nextBtn = document.getElementById("next-step");
    const submitBtn = document.getElementById("submit-form");

    if (prevBtn) {
      prevBtn.style.display = this.currentStep > 1 ? "inline-flex" : "none";
    }

    if (nextBtn) {
      nextBtn.style.display =
        this.currentStep < this.maxStep ? "inline-flex" : "none";
    }

    if (submitBtn) {
      submitBtn.style.display =
        this.currentStep === this.maxStep ? "inline-flex" : "none";
    }
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
   * Validation de l'étape courante
   */
  validateCurrentStep() {
    let isValid = true;

    switch (this.currentStep) {
      case 1:
        isValid = this.validateStep1();
        break;
      case 2:
        isValid = this.validateStep2();
        break;
      case 3:
        isValid = this.validateStep3();
        break;
      case 4:
        isValid = this.validateStep4();
        break;
    }

    if (!isValid) {
      this.showNotification(
        "Veuillez corriger les erreurs avant de continuer",
        "error"
      );
    }

    return isValid;
  }

  /**
   * Validation de l'étape 1
   */
  validateStep1() {
    const requiredFields = [
      "prenom",
      "nom",
      "date_naissance",
      "lieu_naissance",
      "genre",
      "telephone",
      "email",
      "adresse",
    ];

    let isValid = true;

    requiredFields.forEach((fieldId) => {
      const field = document.getElementById(fieldId);
      if (field && !this.validateField(field)) {
        isValid = false;
      }
    });

    return isValid;
  }

  /**
   * Validation de l'étape 2
   */
  validateStep2() {
    const { etablissement, departement, filiere, niveau, anneeAcademique } =
      this.selectionState;

    if (!etablissement || !departement || !filiere || !niveau) {
      this.showNotification(
        "Veuillez compléter toutes les sélections de formation",
        "error"
      );
      return false;
    }

    return true;
  }

  /**
   * Validation de l'étape 3
   */
  validateStep3() {
    const requiredDocs = this.documentsRequired.filter(
      (doc) => doc.est_obligatoire
    );
    const uploadedTypes = this.documentsUploaded.map(
      (doc) => doc.type_document
    );
    const missingRequired = requiredDocs.filter(
      (doc) => !uploadedTypes.includes(doc.type_document)
    );

    if (missingRequired.length > 0) {
      this.showNotification(
        `Documents requis manquants: ${missingRequired
          .map((d) => d.nom)
          .join(", ")}`,
        "error"
      );
      return false;
    }

    return true;
  }

  /**
   * Validation de l'étape 4
   */
  validateStep4() {
    const termsAccepted = document.getElementById("accept_terms")?.checked;

    if (!termsAccepted) {
      this.showNotification(
        "Vous devez accepter les conditions générales",
        "error"
      );
      return false;
    }

    return true;
  }

  /**
   * Validation d'un champ individuel
   */
  validateField(field) {
    const value = field.value.trim();
    const fieldId = field.id;

    // Champ requis vide
    if (field.hasAttribute("required") && !value) {
      this.showFieldError(field, "Ce champ est obligatoire");
      return false;
    }

    // Validations spécifiques par type
    switch (field.type) {
      case "email":
        if (value && !this.config.validation.emailPattern.test(value)) {
          this.showFieldError(field, "Adresse email invalide");
          return false;
        }
        break;

      case "tel":
        if (value && !this.validatePhoneNumber(value)) {
          this.showFieldError(
            field,
            "Numéro de téléphone invalide (+226 XX XX XX XX)"
          );
          return false;
        }
        break;

      case "date":
        if (fieldId === "date_naissance" && value) {
          return this.validateAge();
        }
        break;
    }

    this.clearFieldError(field);
    return true;
  }

  /**
   * Validation de l'âge
   */
  validateAge() {
    const dateField = document.getElementById("date_naissance");
    if (!dateField?.value) return true;

    const birthDate = new Date(dateField.value);
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();

    if (
      monthDiff < 0 ||
      (monthDiff === 0 && today.getDate() < birthDate.getDate())
    ) {
      age--;
    }

    if (age < this.config.validation.minAge) {
      this.showFieldError(
        dateField,
        `Vous devez avoir au moins ${this.config.validation.minAge} ans`
      );
      return false;
    }

    if (age > this.config.validation.maxAge) {
      this.showFieldError(dateField, "Veuillez vérifier la date de naissance");
      return false;
    }

    this.clearFieldError(dateField);
    return true;
  }

  /**
   * Validation du numéro de téléphone
   */
  validatePhoneNumber(phone) {
    const cleanPhone = phone.replace(/\s/g, "");
    return this.config.validation.phonePattern.test(cleanPhone);
  }

  /**
   * Formatage automatique du numéro de téléphone
   */
  formatPhoneNumber(event) {
    let value = event.target.value.replace(/\D/g, "");

    // Enlever l'indicatif pays s'il est présent
    if (value.startsWith("226")) {
      value = value.substring(3);
    }

    if (value.length >= 8) {
      value = value.substring(0, 8);
      value = value.replace(/(\d{2})(\d{2})(\d{2})(\d{2})/, "$1 $2 $3 $4");
    }

    event.target.value = value;
  }

  /**
   * Mise à jour du résumé de l'étape 1
   */
  updateStep1Summary() {
    const prenom = document.getElementById("prenom")?.value || "";
    const nom = document.getElementById("nom")?.value || "";

    if (prenom && nom) {
      this.showElement("step1-summary");
      this.updateElementText("summary-nom-complet", `${prenom} ${nom}`);

      const dateNaissance = document.getElementById("date_naissance")?.value;
      if (dateNaissance) {
        this.updateElementText(
          "summary-date-naissance",
          new Date(dateNaissance).toLocaleDateString("fr-FR")
        );
      }

      const lieuNaissance = document.getElementById("lieu_naissance")?.value;
      this.updateElementText("summary-lieu-naissance", lieuNaissance || "-");

      const telephone = document.getElementById("telephone")?.value;
      this.updateElementText(
        "summary-telephone",
        telephone ? `+226 ${telephone}` : "-"
      );

      const email = document.getElementById("email")?.value;
      this.updateElementText("summary-email", email || "-");
    } else {
      this.hideElement("step1-summary");
    }
  }

  /**
   * Génération du récapitulatif complet
   */
  generateRecapitulatif() {
    this.generatePersonalRecap();
    this.generateFormationRecap();
    this.generateDocumentsRecap();
    this.updateSubmissionStatus();
  }

  /**
   * Génération du récapitulatif personnel
   */
  generatePersonalRecap() {
    // Informations de base
    const prenom = document.getElementById("prenom")?.value || "";
    const nom = document.getElementById("nom")?.value || "";
    const dateNaissance =
      document.getElementById("date_naissance")?.value || "";
    const lieuNaissance =
      document.getElementById("lieu_naissance")?.value || "";
    const genre = document.getElementById("genre")?.value || "";
    const telephone = document.getElementById("telephone")?.value || "";
    const email = document.getElementById("email")?.value || "";
    const adresse = document.getElementById("adresse")?.value || "";

    this.updateElementText(
      "recap-nom-complet",
      `${prenom} ${nom}`.trim() || "-"
    );
    this.updateElementText(
      "recap-date-naissance",
      dateNaissance ? new Date(dateNaissance).toLocaleDateString("fr-FR") : "-"
    );
    this.updateElementText("recap-lieu-naissance", lieuNaissance || "-");
    this.updateElementText(
      "recap-genre",
      genre === "M" ? "Masculin" : genre === "F" ? "Féminin" : "-"
    );
    this.updateElementText(
      "recap-telephone",
      telephone ? `+226 ${telephone}` : "-"
    );
    this.updateElementText("recap-email", email || "-");
    this.updateElementText("recap-adresse", adresse || "-");

    // Informations familiales
    this.updateFamilyInfo();
    this.updateAcademicInfo();
  }

  /**
   * Mise à jour des informations familiales dans le récap
   */
  updateFamilyInfo() {
    const famille = [
      {
        type: "pere",
        nom: document.getElementById("nom_pere")?.value || "",
        tel: document.getElementById("telephone_pere")?.value || "",
      },
      {
        type: "mere",
        nom: document.getElementById("nom_mere")?.value || "",
        tel: document.getElementById("telephone_mere")?.value || "",
      },
      {
        type: "tuteur",
        nom: document.getElementById("nom_tuteur")?.value || "",
        tel: document.getElementById("telephone_tuteur")?.value || "",
      },
    ];

    let hasFamilyInfo = false;

    famille.forEach(({ type, nom, tel }) => {
      const infoElement = document.getElementById(`recap-info-${type}`);
      const itemElement = document.getElementById(`recap-${type}`);

      if (nom || tel) {
        const info = nom + (tel ? ` (+226 ${tel})` : "");
        this.updateElementText(`recap-info-${type}`, info);
        this.showElement(`recap-${type}`);
        hasFamilyInfo = true;
      } else {
        this.hideElement(`recap-${type}`);
      }
    });

    // Afficher/masquer la section famille
    if (hasFamilyInfo) {
      this.showElement("recap-famille");
    } else {
      this.hideElement("recap-famille");
    }
  }

  /**
   * Mise à jour des informations académiques dans le récap
   */
  updateAcademicInfo() {
    const ecole = document.getElementById("ecole_precedente")?.value || "";
    const diplome = document.getElementById("dernier_diplome")?.value || "";
    const annee = document.getElementById("annee_obtention")?.value || "";

    let hasAcademicInfo = false;

    if (ecole) {
      this.updateElementText("recap-ecole-precedente", ecole);
      this.showElement("recap-ecole");
      hasAcademicInfo = true;
    } else {
      this.hideElement("recap-ecole");
    }

    if (diplome) {
      this.updateElementText("recap-dernier-diplome", diplome);
      this.showElement("recap-diplome");
      hasAcademicInfo = true;
    } else {
      this.hideElement("recap-diplome");
    }

    if (annee) {
      this.updateElementText("recap-annee-obtention", annee);
      this.showElement("recap-annee-obtention-item");
      hasAcademicInfo = true;
    } else {
      this.hideElement("recap-annee-obtention-item");
    }

    // Afficher/masquer la section académique
    if (hasAcademicInfo) {
      this.showElement("recap-academique");
    } else {
      this.hideElement("recap-academique");
    }
  }

  /**
   * Génération du récapitulatif formation
   */
  generateFormationRecap() {
    const { etablissement, departement, filiere, niveau, anneeAcademique } =
      this.selectionState;

    if (etablissement && departement && filiere && niveau) {
      this.updateElementText(
        "recap-formation-etablissement",
        etablissement.nom
      );
      this.updateElementText("recap-formation-departement", departement.nom);
      this.updateElementText("recap-formation-filiere", filiere.nom);
      this.updateElementText("recap-formation-niveau", niveau.nom);
      this.updateElementText(
        "recap-formation-annee",
        anneeAcademique ? anneeAcademique.nom : "À définir"
      );

      // Code de formation
      const formationCode = `${etablissement.code}-${departement.code}-${filiere.code}-${niveau.code}`;
      this.updateElementText("recap-formation-code", formationCode);
      this.updateElementText("recap-formation-type", "Formation universitaire");
      this.updateElementText("recap-formation-duree", filiere.duree || "3 ans");
    }
  }

  /**
   * Génération du récapitulatif documents
   */
  generateDocumentsRecap() {
    const requiredDocs = this.documentsRequired.filter(
      (doc) => doc.est_obligatoire
    );
    const optionalDocs = this.documentsRequired.filter(
      (doc) => !doc.est_obligatoire
    );
    const uploadedTypes = this.documentsUploaded.map(
      (doc) => doc.type_document
    );
    const missingRequired = requiredDocs.filter(
      (doc) => !uploadedTypes.includes(doc.type_document)
    );

    // Statistiques
    this.updateElementText("recap-docs-total", this.documentsUploaded.length);
    this.updateElementText("recap-docs-required", requiredDocs.length);
    this.updateElementText("recap-docs-optional", optionalDocs.length);

    // Statut de complétion
    const statusElement = document.getElementById("recap-completion-status");
    const iconElement = document.getElementById("recap-status-icon");
    const textElement = document.getElementById("recap-status-text");

    if (missingRequired.length === 0) {
      if (statusElement) statusElement.className = "completion-status complete";
      this.updateElementText("recap-status-icon", "✅");
      this.updateElementText(
        "recap-status-text",
        "Tous les documents requis ont été téléchargés"
      );
    } else {
      if (statusElement)
        statusElement.className = "completion-status incomplete";
      this.updateElementText("recap-status-icon", "❌");
      this.updateElementText(
        "recap-status-text",
        `${missingRequired.length} document(s) requis manquant(s)`
      );
    }

    // Liste des documents
    this.renderDocumentsRecapList();

    // Documents manquants
    if (missingRequired.length > 0) {
      this.showElement("recap-docs-warning");
      const missingList = document.getElementById("recap-missing-docs-list");
      if (missingList) {
        missingList.innerHTML = missingRequired
          .map((doc) => `<li>${doc.nom}</li>`)
          .join("");
      }
    } else {
      this.hideElement("recap-docs-warning");
    }
  }

  /**
   * Rendu de la liste des documents dans le récap
   */
  renderDocumentsRecapList() {
    const container = document.getElementById("recap-documents-list");
    if (!container) return;

    container.innerHTML = "";

    // Documents téléchargés
    this.documentsUploaded.forEach((doc) => {
      const item = this.createDocumentRecapItem(doc, true);
      container.appendChild(item);
    });

    // Documents manquants requis
    const requiredDocs = this.documentsRequired.filter(
      (doc) => doc.est_obligatoire
    );
    const uploadedTypes = this.documentsUploaded.map(
      (doc) => doc.type_document
    );
    const missingRequired = requiredDocs.filter(
      (doc) => !uploadedTypes.includes(doc.type_document)
    );

    missingRequired.forEach((doc) => {
      const item = this.createDocumentRecapItem(doc, false);
      container.appendChild(item);
    });
  }

  /**
   * Création d'un élément de document dans le récap
   */
  createDocumentRecapItem(doc, isUploaded) {
    const item = document.createElement("div");
    item.className = `doc-recap-item ${isUploaded ? "uploaded" : "missing"}`;

    item.innerHTML = `
            <div class="doc-icon">${this.getFileIcon(
              doc.format_fichier || "pdf"
            )}</div>
            <div class="doc-info">
                <div class="doc-name">${doc.nom}</div>
                <div class="doc-details">
                    ${
                      isUploaded
                        ? `${this.formatFileSize(
                            doc.taille_fichier
                          )} • Téléchargé`
                        : "Document requis • Non téléchargé"
                    }
                </div>
            </div>
            <div class="doc-status">
                <span class="doc-status-badge ${
                  isUploaded ? "uploaded" : "missing"
                }">
                    ${isUploaded ? "Téléchargé" : "Manquant"}
                </span>
            </div>
        `;

    return item;
  }

  /**
   * Mise à jour du statut de soumission
   */
  updateSubmissionStatus() {
    const validations = {
      personal: this.validateStep1(),
      formation: this.validateStep2(),
      documents: this.validateStep3(),
      terms: document.getElementById("accept_terms")?.checked || false,
    };

    // Mise à jour des indicateurs visuels
    Object.entries(validations).forEach(([key, isValid]) => {
      this.updateStatusCheck(`status-${key}`, isValid);
    });

    // Activation/désactivation du bouton de soumission
    const allValid = Object.values(validations).every(Boolean);
    const submitBtn = document.getElementById("submit-form");

    if (submitBtn) {
      submitBtn.disabled = !allValid;

      if (allValid) {
        submitBtn.classList.remove("btn-disabled");
        submitBtn.textContent = "Soumettre la candidature";
      } else {
        submitBtn.classList.add("btn-disabled");
        submitBtn.textContent = "Vérifiez les informations requises";
      }
    }
  }

  /**
   * Mise à jour d'un indicateur de statut
   */
  updateStatusCheck(elementId, isValid) {
    const element = document.getElementById(elementId);
    if (element) {
      element.classList.remove("valid", "invalid");
      element.classList.add(isValid ? "valid" : "invalid");

      const icon = element.querySelector(".check-icon");
      if (icon) {
        icon.textContent = isValid ? "✅" : "❌";
      }
    }
  }

  /**
   * Soumission du formulaire
   */
  async submitForm(event) {
    event.preventDefault();

    if (!this.validateCurrentStep()) {
      return;
    }

    try {
      this.showLoadingState();

      const formData = this.collectFormData();
      const response = await this.submitFormData(formData);

      if (response.success) {
        this.showNotification("Candidature soumise avec succès!", "success");
        this.showSuccessMessage(response);
      } else {
        throw new Error(response.message || "Erreur lors de la soumission");
      }
    } catch (error) {
      console.error("Erreur soumission:", error);
      this.showNotification(
        "Erreur lors de la soumission: " + error.message,
        "error"
      );
    } finally {
      this.hideLoadingState();
    }
  }

  /**
   * Collecte des données du formulaire
   */
  collectFormData() {
    const formData = new FormData();
    const form = document.getElementById("candidature-form");

    // Ajouter les données du formulaire
    const inputs = form.querySelectorAll(
      'input:not([type="file"]), select, textarea'
    );
    inputs.forEach((input) => {
      if (input.type === "checkbox") {
        if (input.checked) {
          formData.append(input.name, input.value || "on");
        }
      } else if (input.value) {
        formData.append(input.name, input.value);
      }
    });

    // Ajouter les fichiers
    this.documentsUploaded.forEach((doc, index) => {
      if (doc.file) {
        formData.append(`document_${index}`, doc.file);
        formData.append(`document_${index}_type`, doc.type_document);
        formData.append(`document_${index}_nom`, doc.nom);
      }
    });

    // Ajouter les métadonnées
    formData.append("selection_state", JSON.stringify(this.selectionState));
    formData.append(
      "documents_count",
      this.documentsUploaded.length.toString()
    );

    return formData;
  }

  /**
   * Envoi des données du formulaire
   */
  async submitFormData(formData) {
    const response = await fetch(this.config.apiEndpoints.submit, {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      return await response.json();
    } else {
      // Si la réponse n'est pas JSON, considérer comme succès
      return {
        success: true,
        message: "Candidature soumise avec succès",
        redirect_url: response.url,
      };
    }
  }

  /**
   * Affichage du message de succès
   */
  showSuccessMessage(response) {
    // Afficher le numéro de candidature si disponible
    if (response.numero_candidature) {
      this.updateElementText(
        "recap-numero-candidature",
        response.numero_candidature
      );
      this.showElement("recap-numero-section");
    }

    // Redirection après délai
    if (response.redirect_url) {
      setTimeout(() => {
        window.location.href = response.redirect_url;
      }, 3000);
    }
  }

  /**
   * États de chargement
   */
  showLoadingState() {
    const submitBtn = document.getElementById("submit-form");
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML =
        '<div class="loader" style="width: 20px; height: 20px; display: inline-block; margin-right: 8px;"></div> Soumission en cours...';
    }
  }

  hideLoadingState() {
    const submitBtn = document.getElementById("submit-form");
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = "Soumettre la candidature";
    }
  }

  // États pour les documents
  showDocumentsLoading() {
    this.showElement("documents-loading");
    this.hideElement("documents-error");
    this.hideElement("documents-list");
  }

  hideDocumentsLoading() {
    this.hideElement("documents-loading");
  }

  showDocumentsError(message) {
    this.hideElement("documents-loading");
    this.showElement("documents-error");
    const errorText = document.querySelector("#documents-error p");
    if (errorText) {
      errorText.textContent =
        message || "Erreur lors du chargement des documents";
    }
  }

  /**
   * Gestion des erreurs de champ
   */
  showFieldError(field, message) {
    const fieldGroup = field.closest(".form-group");
    if (fieldGroup) {
      fieldGroup.classList.add("error");
      const errorElement = fieldGroup.querySelector(".error-message");
      if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = "block";
      }
    }
  }

  clearFieldError(field) {
    const fieldGroup = field.closest(".form-group");
    if (fieldGroup) {
      fieldGroup.classList.remove("error");
      const errorElement = fieldGroup.querySelector(".error-message");
      if (errorElement) {
        errorElement.style.display = "none";
      }
    }
  }

  /**
   * Sauvegarde automatique
   */
  setupAutoSave() {
    // Sauvegarde toutes les 30 secondes
    setInterval(() => {
      this.saveFormData();
    }, this.config.autoSave.interval);

    // Sauvegarde avant fermeture de page
    window.addEventListener("beforeunload", () => {
      this.saveFormData();
    });
  }

  saveFormData() {
    try {
      const formData = {
        currentStep: this.currentStep,
        selectionState: this.selectionState,
        documentsUploaded: this.documentsUploaded.map((doc) => ({
          type_document: doc.type_document,
          nom: doc.nom,
          taille_fichier: doc.taille_fichier,
          format_fichier: doc.format_fichier,
          upload_date: doc.upload_date,
        })),
        timestamp: new Date().toISOString(),
      };

      // Récupérer les valeurs des champs
      const form = document.getElementById("candidature-form");
      if (form) {
        const inputs = form.querySelectorAll("input, select, textarea");
        const values = {};

        inputs.forEach((input) => {
          if (input.type === "checkbox") {
            values[input.name] = input.checked;
          } else if (input.type !== "file") {
            values[input.name] = input.value;
          }
        });

        formData.fieldValues = values;
      }

      localStorage.setItem(this.config.autoSave.key, JSON.stringify(formData));
    } catch (error) {
      console.error("Erreur de sauvegarde automatique:", error);
      this.showNotification(
        "Erreur lors de la sauvegarde automatique",
        "error"
      );
    }
  }
}
