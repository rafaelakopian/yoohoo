<script setup lang="ts">
import { KeyRound, ShieldCheck, HelpCircle } from 'lucide-vue-next'
import { useBrandingStore } from '@/stores/branding'
import { theme } from '@/theme'

const branding = useBrandingStore()
</script>

<template>
  <div :class="theme.page.bgCenter">
    <div class="max-w-lg w-full">
      <div class="text-center mb-8">
        <img
          v-if="branding.currentLogo"
          :src="branding.currentLogo"
          alt="Logo"
          class="w-24 h-24 mx-auto mb-4 rounded-full object-contain shadow-lg"
        />
        <h1 :class="theme.text.h1">Problemen met inloggen?</h1>
        <p :class="theme.text.subtitle">Kies hieronder de optie die bij je situatie past</p>
      </div>

      <div class="space-y-4">
        <!-- Option 1: Forgot password -->
        <div :class="theme.card.padded">
          <div class="flex items-start gap-4">
            <div class="flex-shrink-0 mt-0.5">
              <KeyRound :size="24" class="text-accent-600" />
            </div>
            <div class="flex-1">
              <h3 class="text-base font-semibold text-navy-900 mb-1">Wachtwoord vergeten</h3>
              <p :class="[theme.text.body, 'mb-3']">
                Als je je wachtwoord niet meer weet, kun je via je e-mailadres een nieuw wachtwoord instellen.
              </p>
              <router-link to="/auth/forgot-password" :class="theme.btn.primarySm">
                Wachtwoord resetten
              </router-link>
            </div>
          </div>
        </div>

        <!-- Option 2: 2FA backup codes -->
        <div :class="theme.card.padded">
          <div class="flex items-start gap-4">
            <div class="flex-shrink-0 mt-0.5">
              <ShieldCheck :size="24" class="text-accent-600" />
            </div>
            <div class="flex-1">
              <h3 class="text-base font-semibold text-navy-900 mb-1">2FA code kwijt</h3>
              <p :class="[theme.text.body, 'mb-2']">
                Als je geen toegang meer hebt tot je authenticator-app, kun je inloggen met een van je
                <strong>back-upcodes</strong>. Deze heb je ontvangen toen je 2FA activeerde.
              </p>
              <p :class="theme.text.muted">
                Voer op het inlogscherm je back-upcode in op de plek waar om een verificatiecode wordt gevraagd.
              </p>
            </div>
          </div>
        </div>

        <!-- Option 3: Completely locked out -->
        <div :class="theme.card.padded">
          <div class="flex items-start gap-4">
            <div class="flex-shrink-0 mt-0.5">
              <HelpCircle :size="24" class="text-accent-600" />
            </div>
            <div class="flex-1">
              <h3 class="text-base font-semibold text-navy-900 mb-1">Helemaal buitengesloten</h3>
              <p :class="theme.text.body">
                Kun je niet meer inloggen en heb je geen back-upcodes meer? Neem dan contact op
                met je schoolbeheerder of de platformadmin. Zij kunnen je 2FA resetten zodat je
                weer toegang krijgt tot je account.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div class="text-center mt-6">
        <router-link to="/auth/login" :class="theme.link.primary" class="text-sm">
          Terug naar inloggen
        </router-link>
      </div>
    </div>
  </div>
</template>
