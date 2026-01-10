"""
Configuration Validator
Validates all environment variables and connections before deployment
"""

import os
import sys
from typing import Dict, List, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ConfigValidator:
    """Validates configuration and environment setup"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
    
    def check_required_env_vars(self) -> bool:
        """Check all required environment variables are set"""
        print("\n" + "=" * 60)
        print("Checking Required Environment Variables")
        print("=" * 60)
        
        required_vars = {
            'AZURE_OPENAI_API_KEY': 'Azure OpenAI API Key',
            'AZURE_OPENAI_ENDPOINT': 'Azure OpenAI Endpoint',
            'AZURE_OPENAI_MODEL_DEPLOYMENT_NAME': 'Model Deployment Name (e.g., gpt-4o-mini)',
            'AZURE_OPENAI_EMBEDDING_DEPLOYMENT': 'Embedding Deployment Name',
            'AZURE_SEARCH_KEY': 'Azure AI Search API Key',
            'AZURE_SEARCH_ENDPOINT': 'Azure AI Search Endpoint'
        }
        
        all_present = True
        
        for var_name, description in required_vars.items():
            value = os.environ.get(var_name)
            
            if not value:
                print(f"❌ MISSING: {var_name} ({description})")
                self.errors.append(f"Missing required variable: {var_name}")
                all_present = False
            else:
                # Mask sensitive values
                if 'KEY' in var_name or 'SECRET' in var_name:
                    display_value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
                else:
                    display_value = value
                
                print(f"✅ FOUND: {var_name}")
                print(f"   Value: {display_value}")
        
        return all_present
    
    def check_optional_env_vars(self) -> None:
        """Check optional environment variables for Teams bot"""
        print("\n" + "=" * 60)
        print("Checking Optional Environment Variables (Teams Bot)")
        print("=" * 60)
        
        optional_vars = {
            'CLIENT_ID': 'Azure App Registration Client ID',
            'CLIENT_SECRET': 'Azure App Registration Client Secret',
            'TENANT_ID': 'Azure Tenant ID',
            'BOT_TYPE': 'Bot Authentication Type (UserAssignedMsi, etc.)'
        }
        
        for var_name, description in optional_vars.items():
            value = os.environ.get(var_name)
            
            if not value:
                print(f"⚠️  NOT SET: {var_name} ({description})")
                self.warnings.append(f"Optional variable not set: {var_name}")
            else:
                if 'SECRET' in var_name or 'ID' in var_name:
                    display_value = value[:8] + "..." if len(value) > 8 else "***"
                else:
                    display_value = value
                
                print(f"✅ FOUND: {var_name}")
                print(f"   Value: {display_value}")
    
    def validate_endpoint_formats(self) -> bool:
        """Validate endpoint URL formats"""
        print("\n" + "=" * 60)
        print("Validating Endpoint Formats")
        print("=" * 60)
        
        all_valid = True
        
        # Check OpenAI endpoint
        openai_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', '')
        if openai_endpoint:
            if not openai_endpoint.startswith('https://'):
                print(f"❌ AZURE_OPENAI_ENDPOINT must start with https://")
                self.errors.append("Invalid OpenAI endpoint format")
                all_valid = False
            elif not '.openai.azure.com' in openai_endpoint:
                print(f"⚠️  AZURE_OPENAI_ENDPOINT doesn't look like standard Azure OpenAI format")
                self.warnings.append("Unusual OpenAI endpoint format")
            else:
                print(f"✅ AZURE_OPENAI_ENDPOINT format is valid")
        
        # Check Search endpoint
        search_endpoint = os.environ.get('AZURE_SEARCH_ENDPOINT', '')
        if search_endpoint:
            if not search_endpoint.startswith('https://'):
                print(f"❌ AZURE_SEARCH_ENDPOINT must start with https://")
                self.errors.append("Invalid Search endpoint format")
                all_valid = False
            elif not '.search.windows.net' in search_endpoint:
                print(f"⚠️  AZURE_SEARCH_ENDPOINT doesn't look like standard Azure Search format")
                self.warnings.append("Unusual Search endpoint format")
            else:
                print(f"✅ AZURE_SEARCH_ENDPOINT format is valid")
        
        return all_valid
    
    def check_file_structure(self) -> bool:
        """Check required files exist"""
        print("\n" + "=" * 60)
        print("Checking File Structure")
        print("=" * 60)
        
        required_files = [
            'app.py',
            'config.py',
            'custom_ai_model.py',
            'azure_ai_search_data_source.py',
            'instructions.txt',
            'requirements.txt',
            '.env'
        ]
        
        all_present = True
        
        for filename in required_files:
            if os.path.exists(filename):
                size = os.path.getsize(filename)
                print(f"✅ FOUND: {filename} ({size} bytes)")
            else:
                print(f"❌ MISSING: {filename}")
                self.errors.append(f"Missing required file: {filename}")
                all_present = False
        
        return all_present
    
    def check_instructions_quality(self) -> bool:
        """Validate instructions.txt content"""
        print("\n" + "=" * 60)
        print("Validating instructions.txt Quality")
        print("=" * 60)
        
        try:
            with open('instructions.txt', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for key sections
            required_sections = [
                'ROLE AND OBJECTIVE',
                'KNOWLEDGE BASE',
                'Record Type',
                'RESPONSE GUIDELINES',
                'Unit of Measure'
            ]
            
            all_found = True
            for section in required_sections:
                if section in content:
                    print(f"✅ Found section: {section}")
                else:
                    print(f"❌ Missing section: {section}")
                    self.errors.append(f"Instructions missing section: {section}")
                    all_found = False
            
            # Check length
            word_count = len(content.split())
            print(f"\n📊 Instructions statistics:")
            print(f"   Total characters: {len(content)}")
            print(f"   Total words: {word_count}")
            
            if word_count < 500:
                print(f"⚠️  Instructions seem short (< 500 words)")
                self.warnings.append("Instructions may be incomplete")
            
            return all_found
            
        except FileNotFoundError:
            print(f"❌ instructions.txt not found")
            return False
        except Exception as e:
            print(f"❌ Error reading instructions.txt: {e}")
            return False
    
    def check_model_configuration(self) -> bool:
        """Validate model deployment names"""
        print("\n" + "=" * 60)
        print("Validating Model Configuration")
        print("=" * 60)
        
        model_deployment = os.environ.get('AZURE_OPENAI_MODEL_DEPLOYMENT_NAME', '')
        embedding_deployment = os.environ.get('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', '')
        
        valid = True
        
        # Check model deployment
        if 'gpt-4o-mini' in model_deployment.lower():
            print(f"✅ Using recommended model: {model_deployment}")
        elif 'gpt-4' in model_deployment.lower():
            print(f"✅ Using GPT-4 model: {model_deployment}")
        elif 'gpt-35' in model_deployment.lower():
            print(f"⚠️  Using GPT-3.5: {model_deployment}")
            self.warnings.append("Consider upgrading to gpt-4o-mini for better performance")
        else:
            print(f"⚠️  Unusual model name: {model_deployment}")
            self.warnings.append("Verify model deployment name is correct")
        
        # Check embedding deployment
        if 'text-embedding' in embedding_deployment.lower():
            print(f"✅ Using text embedding model: {embedding_deployment}")
        else:
            print(f"⚠️  Unusual embedding model: {embedding_deployment}")
            self.warnings.append("Verify embedding deployment name is correct")
        
        return valid
    
    def generate_report(self) -> Tuple[bool, Dict]:
        """Generate final validation report"""
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        
        if error_count == 0:
            print(f"\n✅ ALL CRITICAL CHECKS PASSED")
        else:
            print(f"\n❌ FOUND {error_count} CRITICAL ERROR(S)")
        
        if warning_count > 0:
            print(f"⚠️  Found {warning_count} warning(s)")
        
        # Print errors
        if self.errors:
            print(f"\n❌ ERRORS ({error_count}):")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")
        
        # Print warnings
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({warning_count}):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")
        
        # Deployment readiness
        print("\n" + "=" * 80)
        if error_count == 0:
            print("🚀 READY FOR DEPLOYMENT")
            print("\nNext steps:")
            print("1. Run: python test_agent.py")
            print("2. Deploy to Azure App Service")
            print("3. Monitor logs for any runtime issues")
        else:
            print("🛑 NOT READY FOR DEPLOYMENT")
            print("\nPlease fix the errors above before deploying.")
        print("=" * 80)
        
        return error_count == 0, {
            'errors': self.errors,
            'warnings': self.warnings,
            'is_valid': error_count == 0
        }
    
    def run_all_checks(self) -> Tuple[bool, Dict]:
        """Run all validation checks"""
        print("\n" + "=" * 80)
        print("GOODYEAR RAG AGENT - CONFIGURATION VALIDATOR")
        print("=" * 80)
        
        # Run all checks
        checks = [
            self.check_required_env_vars(),
            self.validate_endpoint_formats(),
            self.check_file_structure(),
            self.check_instructions_quality(),
            self.check_model_configuration()
        ]
        
        # Check optional vars (doesn't affect validity)
        self.check_optional_env_vars()
        
        # Generate report
        return self.generate_report()


def main():
    """Main execution"""
    validator = ConfigValidator()
    is_valid, report = validator.run_all_checks()
    
    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()