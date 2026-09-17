export default defineAppConfig({
  ui: {
    colors: {
      // The ramp defined in assets/css/main.css, which is the QAQC dashboard's.
      //
      // Naming a Tailwind colour `primary` does not tell Nuxt UI to use it: the
      // component library keeps its own idea of what primary means and reads it
      // from here. With no app config it fell back to its built-in default,
      // green, so every u-button, u-input, u-alert and u-badge read green while
      // everything hand-written around them read blue.
      primary: 'primary',
    },
  },
})
