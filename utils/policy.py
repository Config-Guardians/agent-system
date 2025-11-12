def retrieve_policy(filename: str) -> str:
    """
    Retrieves policy that is most appropriate for file with filename
    """
    match filename:
        case "application.properties":
            return "policy/deny-application-properties.rego"
        case filename if filename.endswith('.tf'):
            with open(f'tmp/{filename}', 'r') as f:
                content = f.read()
                if "aws_s3_bucket" in content:
                    return "policy/deny-s3.rego"
                elif "aws_ecr_repository" in content:
                    return "policy/deny-ecr.rego"
    raise Exception("Appropriate policy could not be found for given file.")
