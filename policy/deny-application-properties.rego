package main
import rego.v1

# --- 1. Hardcoded DB password ---
deny contains msg if {
    password := input["spring.datasource.password"]
    start := substring(password, 0, 2)
    start != "${"

    end := substring(password, count(password)-1, 1)
    end != "}"
    msg := "Hardcoded DB password found. Use environment variables."
}

# --- 2. Exposes all actuator endpoints ---
deny contains msg if {
    endpoints := input["management.endpoints.web.exposure.include"]
    endpoints == "*"
    msg := "Exposes all actuator endpoints. Only expose what is needed."
}

# --- 3. Actuator health details always exposed ---
deny contains msg if {
    details := input["management.endpoint.health.show-details"]
    details == "always"
    msg := "Actuator health details exposed. Use 'when-authorized' instead."
}

# --- 4. Logging level too verbose ---
deny contains msg if {
    level := input["logging.level.root"]
    lower(level) == "debug"
    msg := "Debug logging enabled. Set logging.level.root to INFO or higher in production."
}

# --- 5. Hardcoded OAuth2 client secret ---
deny contains msg if {
    secret := input["security.oauth2.client.client-secret"]
    start := substring(secret, 0, 2)
    start != "${"

    end := substring(secret, count(secret)-1, 1)
    end != "}"
    msg := "Hardcoded OAuth2 client secret found. Use environment variables."
}

# --- 6. Hardcoded JWT secret ---
deny contains msg if {
    jwt := input["jwt.secret"]
    start := substring(jwt, 0, 2)
    start != "${"

    end := substring(jwt, count(jwt)-1, 1)
    end != "}"
    msg := "Hardcoded JWT secret found. Use environment variables."
}

# --- 7. Permissive CORS policy ---
deny contains msg if {
    cors := input["app.cors.allowed-origins"]
    cors == "*"
    msg := "CORS allowed for all origins. Restrict allowed origins."
}

# --- 8. Insecure upload directory ---
deny contains msg if {
    upload_dir := input["file.upload-dir"]
    start := substring(upload_dir, 0, 2)
    start != "${"

    end := substring(upload_dir, count(upload_dir)-1, 1)
    end != "}"
    msg := "Hardcoded file upload directory found. Use a persistent and restricted directory with environment variables"
}

# --- 9. Hardcoded mail password ---
deny contains msg if {
    mailpass := input["spring.mail.password"]
    start := substring(mailpass, 0, 2)
    start != "${"

    end := substring(mailpass, count(mailpass)-1, 1)
    end != "}"
    msg := "Hardcoded mail password found. Use environment variables."
}

# --- 10. Debug mode enabled ---
deny contains msg if {
    debug := input["app.debug"]
    lower(debug) == "true"
    msg := "Debug mode enabled. Disable debug in production."
}

# --- 11. Admin interface open ---
deny contains msg if {
    admin_open := input["app.admin.open"]
    lower(admin_open) == "true"
    msg := "Administrative interface open. Restrict or disable in production."
}
