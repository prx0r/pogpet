/**
 * MythicBee — Live Preview Renderer
 * Renders product previews in real-time as the user fills in the form
 */

class PreviewRenderer {
  constructor(container) {
    this.container = container;
    this.currentTemplate = null;
    this.currentData = {};
    this.userPhoto = null;
  }

  setTemplate(template) {
    this.currentTemplate = template;
    this.currentData = {};
    this.render();
  }

  updateField(key, value) {
    this.currentData[key] = value;
    this.render();
  }

  setPhoto(dataUrl) {
    this.userPhoto = dataUrl;
    this.render();
  }

  render() {
    if (!this.currentTemplate) {
      this.container.innerHTML = `
        <div class="preview-empty">
          <div class="preview-empty__icon">✦</div>
          <p>Choose a template to see your preview</p>
        </div>`;
      return;
    }

    const t = this.currentTemplate;
    const d = this.currentData;
    const style = t.preview;

    switch (t.layout) {
      case "newspaper":
        this.renderNewspaper(t, d, style);
        break;
      case "biography":
        this.renderBiography(t, d, style);
        break;
      case "storybook":
        this.renderStorybook(t, d, style);
        break;
      case "poster":
        this.renderPoster(t, d, style);
        break;
      case "card":
        this.renderCard(t, d, style);
        break;
    }
  }

  renderNewspaper(t, d, style) {
    this.container.innerHTML = `
      <div class="preview preview--newspaper" style="background:${style.bg}; font-family:${style.bodyFont}">
        <div class="preview__header" style="background:${style.headerBg}; color:${style.headerColor}; font-family:${style.fontFamily}">
          <div class="preview__masthead">THE MYTHIC TIMES</div>
          <div class="preview__date">${new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}</div>
        </div>
        <div class="preview__body">
          ${this.userPhoto ? `<div class="preview__photo"><img src="${this.userPhoto}" alt="Their photo"></div>` : ''}
          <h1 class="preview__headline" contenteditable="true" data-field="headline" style="font-family:${style.fontFamily}">
            ${d.headline || 'HEADLINE HERE'}
          </h1>
          <p class="preview__subhead" contenteditable="true" data-field="subhead">
            ${d.subhead || 'Subheading goes here'}
          </p>
          <div class="preview__columns">
            <div class="preview__column" contenteditable="true" data-field="body">
              ${d.body ? d.body.replace(/\n/g, '<br>') : 'Your story will appear here...'}
            </div>
          </div>
          ${d.quote ? `<blockquote class="preview__quote" contenteditable="true" data-field="quote">"${d.quote}"</blockquote>` : ''}
        </div>
      </div>`;
    this.setupEditableFields();
  }

  renderBiography(t, d, style) {
    this.container.innerHTML = `
      <div class="preview preview--biography" style="background:${style.bg}; font-family:${style.bodyFont}">
        <div class="preview__cover">
          ${this.userPhoto ? `<div class="preview__photo preview__photo--cover"><img src="${this.userPhoto}" alt="Cover photo"></div>` : ''}
          <div class="preview__title-block" style="font-family:${style.fontFamily}">
            <h1 class="preview__title" contenteditable="true" data-field="title">
              ${d.title || 'Book Title'}
            </h1>
            <p class="preview__author" contenteditable="true" data-field="name">
              ${d.name || 'Author Name'}
            </p>
          </div>
        </div>
        <div class="preview__chapters">
          ${d.chapter1 ? `<div class="preview__chapter" contenteditable="true" data-field="chapter1"><h3>Chapter 1</h3><p>${d.chapter1}</p></div>` : ''}
          ${d.chapter2 ? `<div class="preview__chapter" contenteditable="true" data-field="chapter2"><h3>Chapter 2</h3><p>${d.chapter2}</p></div>` : ''}
          ${d.chapter3 ? `<div class="preview__chapter" contenteditable="true" data-field="chapter3"><h3>Chapter 3</h3><p>${d.chapter3}</p></div>` : ''}
        </div>
      </div>`;
    this.setupEditableFields();
  }

  renderStorybook(t, d, style) {
    this.container.innerHTML = `
      <div class="preview preview--storybook" style="background:${style.bg}; font-family:${style.bodyFont}">
        <div class="preview__cover" style="font-family:${style.fontFamily}">
          <h1 class="preview__title" contenteditable="true" data-field="title">
            ${d.title || 'Story Title'}
          </h1>
        </div>
        <div class="preview__pages">
          ${d.page1 ? `
            <div class="preview__page">
              <p contenteditable="true" data-field="page1">${d.page1}</p>
              ${this.userPhoto ? `<div class="preview__photo preview__photo--page"><img src="${this.userPhoto}" alt="Page photo"></div>` : ''}
            </div>` : ''}
          ${d.page2 ? `<div class="preview__page"><p contenteditable="true" data-field="page2">${d.page2}</p></div>` : ''}
          ${d.page3 ? `<div class="preview__page"><p contenteditable="true" data-field="page3">${d.page3}</p></div>` : ''}
        </div>
      </div>`;
    this.setupEditableFields();
  }

  renderPoster(t, d, style) {
    this.container.innerHTML = `
      <div class="preview preview--poster" style="background:${style.bg}; color:${style.accent}; font-family:${style.fontFamily}">
        ${this.userPhoto ? `<div class="preview__photo preview__photo--poster"><img src="${this.userPhoto}" alt="Poster photo"></div>` : ''}
        <h1 class="preview__headline" contenteditable="true" data-field="headline">
          ${d.headline || 'HEADLINE'}
        </h1>
        <p class="preview__subtext" contenteditable="true" data-field="subtext">
          ${d.subtext || 'Subtext'}
        </p>
      </div>`;
    this.setupEditableFields();
  }

  renderCard(t, d, style) {
    this.container.innerHTML = `
      <div class="preview preview--card" style="background:${style.bg}; font-family:${style.bodyFont}">
        <div class="preview__card-inner">
          ${this.userPhoto ? `<div class="preview__photo preview__photo--card"><img src="${this.userPhoto}" alt="Card photo"></div>` : ''}
          <p class="preview__message" contenteditable="true" data-field="message">
            ${d.message || 'Your message here...'}
          </p>
          <p class="preview__from" contenteditable="true" data-field="from">
            ${d.from || 'From'}
          </p>
        </div>
      </div>`;
    this.setupEditableFields();
  }

  setupEditableFields() {
    this.container.querySelectorAll('[contenteditable="true"]').forEach(el => {
      el.addEventListener('input', (e) => {
        const field = e.target.dataset.field;
        const value = e.target.textContent;
        this.currentData[field] = value;
        document.dispatchEvent(new CustomEvent('preview:field-changed', {
          detail: { field, value }
        }));
      });
      el.addEventListener('blur', (e) => {
        e.target.classList.remove('editing');
      });
      el.addEventListener('focus', (e) => {
        e.target.classList.add('editing');
      });
    });
  }

  getData() {
    return { ...this.currentData, photo: this.userPhoto };
  }
}

export default PreviewRenderer;
