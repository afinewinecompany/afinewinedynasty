// Google OAuth integration utilities

declare global {
  interface Window {
    google: {
      accounts: {
        id: {
          initialize: (config: any) => void;
          prompt: () => void;
          renderButton: (element: HTMLElement, config: any) => void;
          disableAutoSelect: () => void;
        };
        oauth2: {
          initCodeClient: (config: any) => {
            requestCode: () => void;
          };
        };
      };
    };
  }
}

interface GoogleOAuthConfig {
  clientId: string;
  redirectUri: string;
  scope?: string;
}

interface GoogleCodeResponse {
  code: string;
  state?: string;
  error?: string;
}

class GoogleOAuth {
  private static instance: GoogleOAuth;
  private config: GoogleOAuthConfig;
  private codeClient: any;

  constructor(config: GoogleOAuthConfig) {
    this.config = config;
  }

  static getInstance(config?: GoogleOAuthConfig): GoogleOAuth {
    if (!GoogleOAuth.instance) {
      if (!config) {
        throw new Error(
          'GoogleOAuth configuration is required for the first initialization'
        );
      }
      GoogleOAuth.instance = new GoogleOAuth(config);
    }
    return GoogleOAuth.instance;
  }

  async initialize(): Promise<void> {
    // Load Google Identity Services script
    if (!window.google) {
      await this.loadGoogleScript();
    }

    // Initialize the OAuth2 code client
    this.codeClient = window.google.accounts.oauth2.initCodeClient({
      client_id: this.config.clientId,
      scope: this.config.scope || 'openid email profile',
      redirect_uri: this.config.redirectUri,
      callback: this.handleCodeResponse.bind(this),
    });
  }

  private loadGoogleScript(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (document.querySelector('script[src*="accounts.google.com"]')) {
        resolve();
        return;
      }

      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () =>
        reject(new Error('Failed to load Google Identity Services'));
      document.head.appendChild(script);
    });
  }

  async signIn(): Promise<GoogleCodeResponse> {
    if (!this.codeClient) {
      await this.initialize();
    }

    return new Promise((resolve, reject) => {
      this.codeClient.callback = (response: GoogleCodeResponse) => {
        if (response.error) {
          reject(new Error(response.error));
        } else {
          resolve(response);
        }
      };

      this.codeClient.requestCode();
    });
  }

  private handleCodeResponse(response: GoogleCodeResponse) {
    if (response.error) {
      console.error('Google OAuth error:', response.error);
      return;
    }

    // This will be handled by the promise in signIn()
    console.log('Google OAuth code received:', response.code);
  }

  renderSignInButton(
    element: HTMLElement,
    options: {
      theme?: 'outline' | 'filled_blue' | 'filled_black';
      size?: 'large' | 'medium' | 'small';
      text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
      shape?: 'rectangular' | 'pill' | 'circle' | 'square';
      width?: number;
      locale?: string;
    } = {}
  ) {
    if (!window.google) {
      console.error('Google Identity Services not loaded');
      return;
    }

    const config = {
      theme: options.theme || 'outline',
      size: options.size || 'large',
      text: options.text || 'signin_with',
      shape: options.shape || 'rectangular',
      width: options.width || 250,
      locale: options.locale || 'en',
      click_listener: () => {
        this.signIn().catch(console.error);
      },
    };

    window.google.accounts.id.renderButton(element, config);
  }
}

export { GoogleOAuth, type GoogleCodeResponse, type GoogleOAuthConfig };
