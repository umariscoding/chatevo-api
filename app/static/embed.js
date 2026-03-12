(function() {
  'use strict';

  // Get minimum config from script tag
  const scriptTag = document.currentScript;
  const companySlug = scriptTag?.getAttribute('data-company-slug');
  const apiUrl = scriptTag?.getAttribute('data-api-url') || 'http://localhost:8000';

  if (!companySlug) {
    console.error('ChatEvo Widget: Missing data-company-slug attribute');
    return;
  }

  // Fallback values from data attributes
  const fallbackConfig = {
    position: scriptTag?.getAttribute('data-position') || 'bottom-right',
    primaryColor: scriptTag?.getAttribute('data-primary-color') || '#6366f1',
    theme: scriptTag?.getAttribute('data-theme') || 'dark',
    welcomeText: scriptTag?.getAttribute('data-welcome-text') || 'Hi there! How can we help you today?',
    subtitleText: scriptTag?.getAttribute('data-subtitle-text') || 'We typically reply instantly',
    headerColor: '',
    placeholderText: 'Type your message...',
    initialMessage: '',
    hideBranding: false,
    autoOpenDelay: 0,
    buttonIcon: 'chat',
    botDisplayName: '',
    chatTemplate: 'default',
  };

  // Fetch settings from backend, then initialize widget
  async function loadAndInit() {
    let config = { ...fallbackConfig };

    try {
      const res = await fetch(`${apiUrl}/public/chatbot/${companySlug}/embed-settings`);
      if (res.ok) {
        const data = await res.json();
        const s = data.settings;
        if (s) {
          config.theme = s.theme || config.theme;
          config.position = (s.position === 'left' ? 'bottom-left' : 'bottom-right');
          config.primaryColor = s.primaryColor || config.primaryColor;
          config.welcomeText = s.welcomeText || config.welcomeText;
          config.subtitleText = s.subtitleText || config.subtitleText;
          config.placeholderText = s.placeholderText || config.placeholderText;
          config.initialMessage = s.initialMessage ?? config.initialMessage;
          config.hideBranding = s.hideBranding ?? config.hideBranding;
          config.autoOpenDelay = s.autoOpenDelay ?? config.autoOpenDelay;
          config.buttonIcon = s.buttonIcon || config.buttonIcon;
          config.headerColor = s.headerColor ?? config.headerColor;
          config.botDisplayName = s.botDisplayName ?? config.botDisplayName;
          config.chatTemplate = s.chatTemplate || config.chatTemplate;
        }
      }
    } catch (e) {
      // Use fallback config
    }

    initWidget(config);
  }

  function initWidget(config) {
    const {
      position, primaryColor, headerColor, theme, welcomeText, subtitleText,
      placeholderText, initialMessage, hideBranding, autoOpenDelay,
      buttonIcon, botDisplayName, chatTemplate
    } = config;

    const resolvedHeaderColor = headerColor || primaryColor;

    // Widget State
    let isOpen = false;
    let chatId = null;
    let messages = [];
    let isLoading = false;
    let companyInfo = null;
    let hasShownInitialMessage = false;

    // Theme colors
    const darkColors = {
      bg: '#09090b',
      bgInput: '#27272a',
      text: '#e4e4e7',
      textSecondary: '#a1a1aa',
      textMuted: '#71717a',
      border: '#27272a',
      scrollbar: '#3f3f46',
      focusRing: '#3f3f46',
    };

    const lightColors = {
      bg: '#ffffff',
      bgInput: '#f4f4f5',
      text: '#18181b',
      textSecondary: '#3f3f46',
      textMuted: '#71717a',
      border: '#e4e4e7',
      scrollbar: '#d4d4d8',
      focusRing: '#d4d4d8',
    };

    const colors = theme === 'light' ? lightColors : darkColors;

    // Button icon SVGs
    const buttonIcons = {
      chat: `<svg class="chat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>`,
      message: `<svg class="chat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>`,
      headset: `<svg class="chat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 18v-6a9 9 0 0 1 18 0v6"></path><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path></svg>`,
      sparkle: `<svg class="chat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l1.912 5.813a2 2 0 0 0 1.275 1.275L21 12l-5.813 1.912a2 2 0 0 0-1.275 1.275L12 21l-1.912-5.813a2 2 0 0 0-1.275-1.275L3 12l5.813-1.912a2 2 0 0 0 1.275-1.275L12 3z"></path></svg>`,
      bolt: `<svg class="chat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>`,
      help: `<svg class="chat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`,
      robot: `<svg class="chat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path><line x1="8" y1="16" x2="8" y2="16"></line><line x1="16" y1="16" x2="16" y2="16"></line></svg>`,
    };

    const selectedIcon = buttonIcons[buttonIcon] || buttonIcons.chat;
    const closeIcon = `<svg class="close-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
    const sendIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>`;

    // Template-specific values
    const isBubbles = chatTemplate === 'bubbles';
    const isMinimal = chatTemplate === 'minimal';

    const modalRadius = isBubbles ? '24px' : isMinimal ? '8px' : '16px';
    const headerRadius = isBubbles ? '24px 24px 0 0' : isMinimal ? '8px 8px 0 0' : '16px 16px 0 0';
    const toggleRadius = isMinimal ? '12px' : '50%';
    const inputRadius = isBubbles ? '28px' : isMinimal ? '8px' : '24px';
    const modalShadow = isMinimal
      ? `0 8px 30px rgba(0, 0, 0, ${theme === 'light' ? '0.1' : '0.4'})`
      : `0 20px 50px rgba(0, 0, 0, ${theme === 'light' ? '0.15' : '0.5'})`;

    // Header styling per template
    const headerBg = isMinimal ? colors.bg : resolvedHeaderColor;
    const headerBorder = isMinimal ? `border-bottom: 1px solid ${colors.border};` : '';
    const headerTitleColor = isMinimal ? colors.text : '#ffffff';
    const headerSubtitleColor = isMinimal ? colors.textMuted : 'rgba(255, 255, 255, 0.7)';
    const headerPadding = isBubbles ? '20px 16px' : isMinimal ? '14px 16px' : '16px';
    const headerTitleSize = isMinimal ? '14px' : '16px';
    const headerTitleWeight = isMinimal ? '600' : isBubbles ? '600' : '500';
    const headerSubtitleSize = isMinimal ? '11px' : '12px';

    // Close button per template
    const closeBtnRadius = isBubbles ? '16px' : isMinimal ? '6px' : '8px';
    const closeBtnColor = isMinimal ? colors.textMuted : 'rgba(255, 255, 255, 0.7)';
    const closeBtnHoverBg = isMinimal ? (theme === 'light' ? '#f4f4f5' : '#27272a') : 'rgba(255, 255, 255, 0.15)';
    const closeBtnHoverColor = isMinimal ? colors.text : '#ffffff';
    const closeBtnSize = isMinimal ? '28px' : '32px';
    const closeBtnIconSize = isMinimal ? '16px' : '18px';

    // Bubbles template: close button has bg
    const closeBtnBg = isBubbles ? 'rgba(255,255,255,0.15)' : 'transparent';

    // Send button per template
    const sendBtnBg = isBubbles ? primaryColor : isMinimal ? primaryColor : 'transparent';
    const sendBtnDisabledBg = isBubbles ? colors.bgInput : isMinimal ? 'transparent' : 'transparent';
    const sendBtnColor = isBubbles ? '#ffffff' : isMinimal ? '#ffffff' : colors.textMuted;
    const sendBtnDisabledColor = isBubbles ? colors.textMuted : isMinimal ? colors.textMuted : colors.textMuted;
    const sendBtnSize = isBubbles ? '34px' : isMinimal ? '30px' : '32px';
    const sendBtnRadius = isMinimal ? '6px' : '50%';
    const sendBtnIconSize = isBubbles ? '16px' : isMinimal ? '14px' : '18px';

    // Input area styling
    const inputWrapperBg = isMinimal ? 'transparent' : colors.bgInput;
    const inputWrapperBorder = isMinimal ? `border: 1px solid ${colors.border};` : '';
    const inputPadding = isBubbles ? '8px 8px 8px 18px' : isMinimal ? '8px 8px 8px 12px' : '8px 8px 8px 16px';
    const inputAreaPad = isMinimal ? '12px 14px' : '16px';
    const inputFontSize = isMinimal ? '13px' : '14px';
    const msgAreaPad = isMinimal ? '12px 14px' : '8px 16px';

    // Message styles per template
    let userMsgStyles = '';
    let botMsgContentStyles = '';
    if (isBubbles) {
      userMsgStyles = `
        background: ${primaryColor};
        color: #ffffff;
        border-radius: 20px 20px 4px 20px;
        padding: 10px 16px;
        line-height: 1.5;
      `;
      botMsgContentStyles = `
        background: ${colors.bgInput};
        color: ${colors.text};
        border-radius: 20px 20px 20px 4px;
        padding: 10px 16px;
        line-height: 1.5;
      `;
    } else if (isMinimal) {
      userMsgStyles = `
        background: ${theme === 'light' ? '#f0f0f0' : '#1a1a1e'};
        color: ${colors.text};
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 13px;
        line-height: 1.5;
      `;
      botMsgContentStyles = `
        color: ${colors.textSecondary};
        padding: 6px 0;
        font-size: 13px;
        line-height: 1.6;
      `;
    } else {
      userMsgStyles = `
        background: ${colors.bgInput};
        color: ${colors.text};
        border-radius: 18px;
        padding: 10px 14px;
      `;
      botMsgContentStyles = `
        color: ${colors.textSecondary};
        padding: 4px 0;
        line-height: 1.6;
      `;
    }

    const msgSpacing = isBubbles ? '10px' : isMinimal ? '6px' : '8px';
    const botAvatarSize = isBubbles ? '32px' : '28px';
    const botAvatarFontSize = isBubbles ? '14px' : '13px';

    // CSS Styles with theme + template support
    const styles = `
      .chatevo-widget-container * {
        box-sizing: border-box;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        margin: 0;
        padding: 0;
      }

      .chatevo-toggle-btn {
        position: fixed;
        ${position === 'bottom-left' ? 'left: 20px;' : 'right: 20px;'}
        bottom: 20px;
        width: 56px;
        height: 56px;
        border-radius: ${toggleRadius};
        background: ${primaryColor};
        border: none;
        cursor: pointer;
        box-shadow: 0 4px 20px rgba(0, 0, 0, ${theme === 'light' ? '0.15' : '0.4'});
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
        z-index: 999998;
      }

      .chatevo-toggle-btn:hover {
        transform: scale(1.05);
      }

      .chatevo-toggle-btn svg {
        width: 24px;
        height: 24px;
        color: white;
        transition: all 0.2s ease;
      }

      .chatevo-toggle-btn.open svg.chat-icon {
        opacity: 0;
        transform: scale(0);
      }

      .chatevo-toggle-btn svg.close-icon {
        position: absolute;
        opacity: 0;
        transform: scale(0);
      }

      .chatevo-toggle-btn.open svg.close-icon {
        opacity: 1;
        transform: scale(1);
      }

      .chatevo-modal {
        position: fixed;
        ${position === 'bottom-left' ? 'left: 20px;' : 'right: 20px;'}
        bottom: 88px;
        width: 420px;
        max-width: calc(100vw - 40px);
        height: 600px;
        max-height: calc(100vh - 120px);
        background: ${colors.bg};
        border-radius: ${modalRadius};
        border: 1px solid ${colors.border};
        box-shadow: ${modalShadow};
        display: flex;
        flex-direction: column;
        overflow: hidden;
        z-index: 999999;
        transform: translateY(10px);
        opacity: 0;
        visibility: hidden;
        transition: all 0.2s ease;
      }

      .chatevo-modal.open {
        transform: translateY(0);
        opacity: 1;
        visibility: visible;
      }

      @media (max-width: 480px) {
        .chatevo-modal {
          left: 8px;
          right: 8px;
          bottom: 8px;
          top: 8px;
          width: auto;
          max-width: none;
          height: auto;
          max-height: none;
        }
      }

      .chatevo-header {
        padding: ${headerPadding};
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-shrink: 0;
        background: ${headerBg};
        border-radius: ${headerRadius};
        ${headerBorder}
      }

      .chatevo-header-text {
        display: flex;
        align-items: center;
        gap: ${isBubbles ? '12px' : '0'};
      }

      .chatevo-header-text h3 {
        font-size: ${headerTitleSize};
        font-weight: ${headerTitleWeight};
        color: ${headerTitleColor};
      }

      .chatevo-header-text p {
        font-size: ${headerSubtitleSize};
        color: ${headerSubtitleColor};
        margin-top: ${isMinimal ? '1px' : '2px'};
      }

      .chatevo-header-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: rgba(255,255,255,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 15px;
        font-weight: 600;
        color: white;
        flex-shrink: 0;
      }

      .chatevo-header-avatar-minimal {
        width: 28px;
        height: 28px;
        border-radius: 6px;
        background: ${primaryColor};
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 600;
        color: white;
        flex-shrink: 0;
        margin-right: 10px;
      }

      .chatevo-close-btn {
        width: ${closeBtnSize};
        height: ${closeBtnSize};
        border-radius: ${closeBtnRadius};
        background: ${closeBtnBg};
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        color: ${closeBtnColor};
        transition: all 0.15s;
      }

      .chatevo-close-btn:hover {
        background: ${closeBtnHoverBg};
        color: ${closeBtnHoverColor};
      }

      .chatevo-close-btn svg {
        width: ${closeBtnIconSize};
        height: ${closeBtnIconSize};
      }

      .chatevo-messages {
        flex: 1;
        overflow-y: auto;
        padding: ${msgAreaPad};
        display: flex;
        flex-direction: column;
      }

      .chatevo-messages::-webkit-scrollbar {
        width: 4px;
      }

      .chatevo-messages::-webkit-scrollbar-thumb {
        background: ${colors.scrollbar};
        border-radius: 4px;
      }

      .chatevo-message {
        max-width: 85%;
        margin-bottom: ${msgSpacing};
        animation: chatevo-fadeIn 0.2s ease;
      }

      @keyframes chatevo-fadeIn {
        from { opacity: 0; transform: translateY(4px); }
        to { opacity: 1; transform: translateY(0); }
      }

      .chatevo-message.user {
        align-self: flex-end;
      }

      .chatevo-message.bot-msg {
        display: flex;
        align-items: ${isBubbles ? 'flex-end' : 'flex-start'};
        gap: 8px;
      }

      .chatevo-bot-avatar {
        width: ${botAvatarSize};
        height: ${botAvatarSize};
        border-radius: 50%;
        background: ${primaryColor};
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: ${botAvatarFontSize};
        font-weight: 600;
        color: white;
        flex-shrink: 0;
        margin-top: 2px;
      }

      .chatevo-message.user .chatevo-message-content {
        ${userMsgStyles}
      }

      .chatevo-message:not(.user) .chatevo-message-content {
        ${botMsgContentStyles}
      }

      .chatevo-message-content {
        font-size: 14px;
        white-space: pre-wrap;
        word-break: break-word;
      }

      .chatevo-welcome {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: ${isMinimal ? 'flex-start' : 'center'};
        justify-content: center;
        text-align: ${isMinimal ? 'left' : 'center'};
        padding: ${isBubbles ? '24px' : '20px'};
      }

      .chatevo-welcome h4 {
        font-size: ${isBubbles ? '16px' : isMinimal ? '14px' : '15px'};
        font-weight: ${isBubbles ? '500' : '400'};
        color: ${isBubbles ? colors.text : colors.textSecondary};
        margin-bottom: 4px;
      }

      .chatevo-welcome p {
        font-size: ${isMinimal ? '12px' : '13px'};
        color: ${colors.textMuted};
      }

      .chatevo-welcome-avatar {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        background: ${primaryColor};
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        font-weight: 600;
        color: white;
        margin-bottom: 12px;
      }

      .chatevo-typing {
        display: flex;
        gap: 4px;
        padding: 8px 0;
      }

      .chatevo-typing-dot {
        width: 6px;
        height: 6px;
        background: ${colors.textMuted};
        border-radius: 50%;
        animation: chatevo-bounce 1.4s infinite ease-in-out;
      }

      .chatevo-typing-dot:nth-child(1) { animation-delay: -0.32s; }
      .chatevo-typing-dot:nth-child(2) { animation-delay: -0.16s; }

      @keyframes chatevo-bounce {
        0%, 80%, 100% { opacity: 0.4; }
        40% { opacity: 1; }
      }

      .chatevo-input-area {
        padding: ${inputAreaPad};
        flex-shrink: 0;
      }

      .chatevo-input-wrapper {
        display: flex;
        align-items: center;
        background: ${inputWrapperBg};
        border-radius: ${inputRadius};
        padding: ${inputPadding};
        transition: all 0.15s;
        ${inputWrapperBorder}
      }

      .chatevo-input-wrapper:focus-within {
        ${isMinimal ? `border-color: ${primaryColor}; box-shadow: 0 0 0 1px ${primaryColor}40;` : `box-shadow: 0 0 0 2px ${colors.focusRing};`}
      }

      .chatevo-input {
        flex: 1;
        border: none;
        background: transparent;
        color: ${colors.text};
        font-size: ${inputFontSize};
        resize: none;
        outline: none;
        max-height: 100px;
        min-height: 20px;
        line-height: 20px;
        padding: 0;
      }

      .chatevo-input::placeholder {
        color: ${colors.textMuted};
      }

      .chatevo-send-btn {
        width: ${sendBtnSize};
        height: ${sendBtnSize};
        border-radius: ${sendBtnRadius};
        background: ${sendBtnBg};
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        color: ${sendBtnColor};
        transition: all 0.15s;
        flex-shrink: 0;
      }

      .chatevo-send-btn:hover:not(:disabled) {
        ${isBubbles ? `opacity: 0.9;` : isMinimal ? `opacity: 0.9;` : `color: ${colors.text};`}
      }

      .chatevo-send-btn:disabled {
        ${isBubbles ? `background: ${sendBtnDisabledBg}; color: ${sendBtnDisabledColor}; cursor: not-allowed;`
        : isMinimal ? `background: ${sendBtnDisabledBg}; color: ${sendBtnDisabledColor}; opacity: 0.4; cursor: not-allowed;`
        : `opacity: 0.3; cursor: not-allowed;`}
      }

      .chatevo-send-btn svg {
        width: ${sendBtnIconSize};
        height: ${sendBtnIconSize};
      }

      .chatevo-powered {
        text-align: center;
        padding: 8px;
        font-size: 10px;
        color: ${colors.textMuted};
        border-top: 1px solid ${colors.border};
      }

      .chatevo-powered a {
        color: ${colors.textMuted};
        text-decoration: none;
      }

      .chatevo-powered a:hover {
        color: ${colors.textSecondary};
      }

      .chatevo-cursor {
        display: inline-block;
        width: 2px;
        height: 14px;
        background: ${colors.textMuted};
        margin-left: 2px;
        animation: chatevo-blink 0.8s infinite;
        vertical-align: text-bottom;
      }

      @keyframes chatevo-blink {
        0%, 50% { opacity: 1; }
        51%, 100% { opacity: 0; }
      }
    `;

    // Inject styles
    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles;
    document.head.appendChild(styleSheet);

    // Build powered-by section
    const poweredByHtml = hideBranding
      ? ''
      : `<div class="chatevo-powered">Powered by <a href="https://chatevo.com" target="_blank">ChatEvo</a></div>`;

    // Get bot avatar initial
    const avatarInitial = botDisplayName ? botDisplayName.charAt(0).toUpperCase() : '';

    // Build header avatar based on template
    let headerAvatarHtml = '';
    if (botDisplayName) {
      if (isBubbles) {
        headerAvatarHtml = `<div class="chatevo-header-avatar">${avatarInitial}</div>`;
      } else if (isMinimal) {
        headerAvatarHtml = `<div class="chatevo-header-avatar-minimal">${avatarInitial}</div>`;
      }
    }

    // Build welcome avatar for bubbles template
    let welcomeAvatarHtml = '';
    if (isBubbles && botDisplayName) {
      welcomeAvatarHtml = `<div class="chatevo-welcome-avatar">${avatarInitial}</div>`;
    }

    // Create widget
    const container = document.createElement('div');
    container.className = 'chatevo-widget-container';
    container.innerHTML = `
      <button class="chatevo-toggle-btn" aria-label="Open chat">
        ${selectedIcon}
        ${closeIcon}
      </button>
      <div class="chatevo-modal">
        <div class="chatevo-header">
          <div class="chatevo-header-text">
            ${headerAvatarHtml}
            <div>
              <h3 class="chatevo-title">Chat Assistant</h3>
              <p class="chatevo-subtitle">${subtitleText}</p>
            </div>
          </div>
          <button class="chatevo-close-btn" aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${isMinimal ? '2' : isBubbles ? '2.5' : '2'}"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
        <div class="chatevo-messages">
          <div class="chatevo-welcome">
            ${welcomeAvatarHtml}
            <h4 class="chatevo-welcome-text">${welcomeText}</h4>
            <p>Ask us anything</p>
          </div>
        </div>
        <div class="chatevo-input-area">
          <div class="chatevo-input-wrapper">
            <textarea class="chatevo-input" placeholder="${placeholderText}" rows="1"></textarea>
            <button class="chatevo-send-btn" disabled>
              ${sendIcon}
            </button>
          </div>
        </div>
        ${poweredByHtml}
      </div>
    `;

    document.body.appendChild(container);

    // DOM elements
    const toggleBtn = container.querySelector('.chatevo-toggle-btn');
    const modal = container.querySelector('.chatevo-modal');
    const closeBtn = container.querySelector('.chatevo-close-btn');
    const messagesContainer = container.querySelector('.chatevo-messages');
    const input = container.querySelector('.chatevo-input');
    const sendBtn = container.querySelector('.chatevo-send-btn');
    const headerTitle = container.querySelector('.chatevo-title');

    // Fetch company info
    async function fetchCompanyInfo() {
      try {
        const response = await fetch(`${apiUrl}/public/chatbot/${companySlug}`);
        if (response.ok) {
          companyInfo = await response.json();
          if (companyInfo.chatbot_title) {
            headerTitle.textContent = companyInfo.chatbot_title;
          }
        }
      } catch (e) {
        console.error('ChatEvo Widget: Failed to fetch company info');
      }
    }

    function openChat() {
      isOpen = true;
      modal.classList.add('open');
      toggleBtn.classList.add('open');
      setTimeout(() => input.focus(), 100);
      if (!companyInfo) fetchCompanyInfo();

      // Show initial message on first open
      if (!hasShownInitialMessage && initialMessage) {
        hasShownInitialMessage = true;
        const welcome = messagesContainer.querySelector('.chatevo-welcome');
        if (welcome) welcome.remove();
        addBotMessage(initialMessage);
      }
    }

    function closeChat() {
      isOpen = false;
      modal.classList.remove('open');
      toggleBtn.classList.remove('open');
    }

    function toggleChat() {
      if (isOpen) closeChat();
      else openChat();
    }

    function escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    function scrollToBottom() {
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function addBotMessage(content) {
      const welcome = messagesContainer.querySelector('.chatevo-welcome');
      if (welcome) welcome.remove();

      const div = document.createElement('div');
      div.className = 'chatevo-message bot-msg';

      let avatarHtml = '';
      if (botDisplayName) {
        avatarHtml = `<div class="chatevo-bot-avatar">${avatarInitial}</div>`;
      }

      div.innerHTML = `${avatarHtml}<div class="chatevo-message-content">${escapeHtml(content)}</div>`;
      messagesContainer.appendChild(div);
      scrollToBottom();
      return div;
    }

    function addMessage(content, isUser = false) {
      if (!isUser) return addBotMessage(content);

      const welcome = messagesContainer.querySelector('.chatevo-welcome');
      if (welcome) welcome.remove();

      const div = document.createElement('div');
      div.className = 'chatevo-message user';
      div.innerHTML = `<div class="chatevo-message-content">${escapeHtml(content)}</div>`;
      messagesContainer.appendChild(div);
      scrollToBottom();
      return div;
    }

    function showTyping() {
      const div = document.createElement('div');
      div.className = 'chatevo-message bot-msg';
      div.id = 'chatevo-typing';

      let avatarHtml = '';
      if (botDisplayName) {
        avatarHtml = `<div class="chatevo-bot-avatar">${avatarInitial}</div>`;
      }

      div.innerHTML = `${avatarHtml}<div class="chatevo-typing"><div class="chatevo-typing-dot"></div><div class="chatevo-typing-dot"></div><div class="chatevo-typing-dot"></div></div>`;
      messagesContainer.appendChild(div);
      scrollToBottom();
    }

    function hideTyping() {
      const el = document.getElementById('chatevo-typing');
      if (el) el.remove();
    }

    async function sendMessage() {
      const message = input.value.trim();
      if (!message || isLoading) return;

      isLoading = true;
      input.value = '';
      input.style.height = 'auto';
      sendBtn.disabled = true;

      addMessage(message, true);
      showTyping();

      try {
        const response = await fetch(`${apiUrl}/public/chatbot/${companySlug}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, chat_id: chatId })
        });

        if (!response.ok) throw new Error('Failed');

        hideTyping();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let aiDiv = null;
        let fullResponse = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === 'start') {
                  chatId = data.chat_id;
                } else if (data.type === 'chunk' && data.content) {
                  fullResponse += data.content.replace(/\\n/g, '\n').replace(/\\r/g, '\r').replace(/\\"/g, '"');
                  if (!aiDiv) aiDiv = addBotMessage('');
                  aiDiv.querySelector('.chatevo-message-content').innerHTML = escapeHtml(fullResponse) + '<span class="chatevo-cursor"></span>';
                  scrollToBottom();
                } else if (data.type === 'end' && aiDiv) {
                  const cursor = aiDiv.querySelector('.chatevo-cursor');
                  if (cursor) cursor.remove();
                } else if (data.type === 'error') {
                  throw new Error(data.error);
                }
              } catch (e) {}
            }
          }
        }

        messages.push({ role: 'user', content: message });
        messages.push({ role: 'assistant', content: fullResponse });

      } catch (e) {
        hideTyping();
        addBotMessage('Sorry, something went wrong. Please try again.');
      } finally {
        isLoading = false;
        updateSendButton();
      }
    }

    function updateSendButton() {
      sendBtn.disabled = !input.value.trim() || isLoading;
    }

    function autoResize() {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 100) + 'px';
    }

    // Events
    toggleBtn.addEventListener('click', toggleChat);
    closeBtn.addEventListener('click', closeChat);
    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('input', () => { updateSendButton(); autoResize(); });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && isOpen) closeChat(); });

    fetchCompanyInfo();

    // Auto-open after delay
    if (autoOpenDelay > 0) {
      setTimeout(() => {
        if (!isOpen) openChat();
      }, autoOpenDelay * 1000);
    }
  }

  // Start loading
  loadAndInit();
})();
