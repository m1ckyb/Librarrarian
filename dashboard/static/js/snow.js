/**
 * Christmas Snow Animation
 * Adds subtle falling snowflakes to the page when either Christmas theme is active.
 * Snowflakes are created dynamically and fall from top to bottom with varying speeds and sizes.
 * Works with both Winter Christmas and Summer Christmas themes.
 */

class SnowEffect {
    constructor() {
        this.snowflakes = [];
        this.container = null;
        this.maxSnowflakes = 75; // Maximum number of snowflakes on screen (increased from 50)
        this.animationFrame = null;
        this.isActive = false;
        
        // Define festive colors for Summer Christmas theme
        this.summerColors = [
            { color: 'rgba(39, 174, 96, 0.9)', shadow: '0 0 5px rgba(39, 174, 96, 0.5)' },      // Green
            { color: 'rgba(231, 76, 60, 0.9)', shadow: '0 0 5px rgba(231, 76, 60, 0.5)' },      // Red
            { color: 'rgba(192, 192, 192, 0.9)', shadow: '0 0 5px rgba(192, 192, 192, 0.6)' },  // Silver
            { color: 'rgba(255, 215, 0, 0.9)', shadow: '0 0 5px rgba(255, 215, 0, 0.5)' }       // Gold
        ];
    }

    /**
     * Initialize the snow effect
     */
    init() {
        // Create container for snowflakes
        this.container = document.createElement('div');
        this.container.id = 'snow-container';
        this.container.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 9999;
            overflow: hidden;
        `;
        document.body.appendChild(this.container);
    }

    /**
     * Create a single snowflake element
     */
    createSnowflake() {
        const snowflake = document.createElement('div');
        snowflake.className = 'snowflake';
        snowflake.innerHTML = '❄'; // Unicode snowflake character
        
        // Random properties for natural variation
        const size = Math.random() * 0.8 + 0.4; // Size between 0.4 and 1.2 rem
        const startX = Math.random() * 100; // Random starting X position (%)
        const duration = Math.random() * 10 + 10; // Fall duration between 10-20 seconds
        const delay = Math.random() * 5; // Random start delay up to 5 seconds
        const drift = (Math.random() - 0.5) * 100; // Horizontal drift (-50px to 50px)
        
        // Choose color based on theme
        const currentTheme = document.documentElement.getAttribute('data-bs-theme');
        let color;
        let textShadow;
        
        if (currentTheme === 'summer-christmas') {
            // For Summer Christmas, use festive colors: green, red, silver, gold
            const randomColor = this.summerColors[Math.floor(Math.random() * this.summerColors.length)];
            color = randomColor.color;
            textShadow = randomColor.shadow;
        } else {
            // For Winter Christmas, use white snowflakes
            color = 'rgba(255, 255, 255, 0.8)';
            textShadow = '0 0 5px rgba(255, 255, 255, 0.5)';
        }
        
        snowflake.style.cssText = `
            position: absolute;
            top: -20px;
            left: ${startX}%;
            font-size: ${size}rem;
            color: ${color};
            text-shadow: ${textShadow};
            animation: snowfall ${duration}s linear ${delay}s infinite;
            transform: translateX(0);
            user-select: none;
            pointer-events: none;
        `;
        
        // Store drift value for custom animation
        snowflake.dataset.drift = drift;
        
        return snowflake;
    }

    /**
     * Add CSS keyframe animation for snowfall
     */
    addStyleSheet() {
        if (document.getElementById('snow-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'snow-styles';
        style.textContent = `
            @keyframes snowfall {
                0% {
                    transform: translateY(0) translateX(0) rotate(0deg);
                    opacity: 0;
                }
                10% {
                    opacity: 0.8;
                }
                90% {
                    opacity: 0.8;
                }
                100% {
                    transform: translateY(100vh) translateX(var(--drift, 0px)) rotate(360deg);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Start the snow effect
     */
    start() {
        if (this.isActive) return;
        
        this.isActive = true;
        
        // Add stylesheet if not already present
        this.addStyleSheet();
        
        // Initialize container if not already present
        if (!this.container) {
            this.init();
        }
        
        // Create initial snowflakes
        for (let i = 0; i < this.maxSnowflakes; i++) {
            const snowflake = this.createSnowflake();
            // Set drift as CSS variable for animation
            snowflake.style.setProperty('--drift', `${snowflake.dataset.drift}px`);
            this.container.appendChild(snowflake);
            this.snowflakes.push(snowflake);
        }
        
        console.log('❄ Snow effect started');
    }

    /**
     * Stop the snow effect and clean up
     */
    stop() {
        if (!this.isActive) return;
        
        this.isActive = false;
        
        // Remove all snowflakes
        this.snowflakes.forEach(snowflake => {
            if (snowflake.parentNode) {
                snowflake.parentNode.removeChild(snowflake);
            }
        });
        this.snowflakes = [];
        
        // Remove container
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
            this.container = null;
        }
        
        console.log('❄ Snow effect stopped');
    }
}

// Create global snow effect instance
const snowEffect = new SnowEffect();

// Export for use in other scripts
window.snowEffect = snowEffect;

// Auto-start snow effect if Christmas theme is active on page load
document.addEventListener('DOMContentLoaded', () => {
    const currentTheme = document.documentElement.getAttribute('data-bs-theme');
    if (currentTheme === 'christmas' || currentTheme === 'summer-christmas') {
        snowEffect.start();
    }
});
