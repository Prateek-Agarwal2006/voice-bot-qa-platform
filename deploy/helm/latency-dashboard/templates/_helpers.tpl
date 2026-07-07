{{- define "voicebot-qa.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "voicebot-qa.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "voicebot-qa.labels" -}}
helm.sh/chart: {{ include "voicebot-qa.name" . }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "voicebot-qa.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "voicebot-qa.selectorLabels" -}}
app.kubernetes.io/name: {{ include "voicebot-qa.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* POSTGRES_DSN — injected into every pod that reads/writes DB */}}
{{- define "voicebot-qa.postgresEnv" -}}
- name: POSTGRES_DSN
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secrets.name }}
      key: POSTGRES_DSN
{{- end -}}

{{/* Judge + ElevenLabs API keys — eval worker only */}}
{{- define "voicebot-qa.apiKeysEnv" -}}
- name: ELEVENLABS_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secrets.name }}
      key: ELEVENLABS_API_KEY
- name: OPENAI_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secrets.name }}
      key: OPENAI_API_KEY
      optional: true
- name: ANTHROPIC_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secrets.name }}
      key: ANTHROPIC_API_KEY
      optional: true
- name: GEMINI_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.secrets.name }}
      key: GEMINI_API_KEY
      optional: true
{{- end -}}
