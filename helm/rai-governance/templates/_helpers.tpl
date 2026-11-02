{{/*
Expand the name of the chart.
*/}}
{{- define "rai-governance.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "rai-governance.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart label value.
*/}}
{{- define "rai-governance.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "rai-governance.labels" -}}
helm.sh/chart: {{ include "rai-governance.chart" . }}
{{ include "rai-governance.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "rai-governance.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rai-governance.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
ServiceAccount name.
*/}}
{{- define "rai-governance.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "rai-governance.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Hosted MCP deployment fullname -- distinct from the dashboard's own
fullname so the two Deployments never collide on name or selector
labels (a Deployment's selector is immutable after creation, so this
must stay stable once released, same as the dashboard's).
*/}}
{{- define "rai-governance.mcp.fullname" -}}
{{- printf "%s-mcp" (include "rai-governance.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Hosted MCP selector labels.
*/}}
{{- define "rai-governance.mcp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rai-governance.name" . }}-mcp
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Hosted MCP common labels.
*/}}
{{- define "rai-governance.mcp.labels" -}}
helm.sh/chart: {{ include "rai-governance.chart" . }}
{{ include "rai-governance.mcp.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
