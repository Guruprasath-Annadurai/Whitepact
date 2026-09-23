# AI-CAIQ v1.1 controls outside legacy CCM v4 map (261 keys)

Total ledger rows: 320
Legacy map keys: 261
Supplement entries: 90

Manual evidence review performed via `scripts/csa_star_ai/ai_caiq_supplement.py` and `evidence_assessor.py` (not bulk-flipped from preliminary snapshot).

| Question ID | Response | Strength | Domain | Question (truncated) |
|-------------|----------|----------|--------|---------------------|
| AIS-08.1 | YES | STRONG | AIS | Are processes, procedures and technical measures to secure APIs, including autho |
| AIS-08.2 | NO | WEAK | AIS | Are technical measures for any improvements reviewed and updated at least annual |
| AIS-09.1 | YES | STRONG | AIS | Is the input against adversarial patterns, failure patterns and unwanted behavio |
| AIS-10.1 | YES | STRONG | AIS | Is the output against adversarial patterns, failure patterns and unwanted behavi |
| AIS-11.1 | YES | STRONG | AIS | Are the security boundaries for agents established? |
| AIS-12.1 | YES | MODERATE | AIS | Are source code management practices, such as version control, code review and s |
| AIS-13.1 | NO | WEAK | AIS | Are sandboxing techniques implemented to execute AI tools and plugins in isolate |
| AIS-14.1 | NO | WEAK | AIS | Are security measures implemented to protect cache systems in GenAI systems and  |
| AIS-15.1 | NO | WEAK | AIS | Are mechanisms implemented to enable the model to clearly distinguish user-provi |
| BCR-02.2 | NO | WEAK | BCR | Is the risk assessment and impact analysis, reviewed and updated at least annual |
| CCC-06.2 | NO | WEAK | CCC | Are the baselines reviewed and updated at least annually or upon significant cha |
| DCS-03.3 | NA | MODERATE | DCS | Are policies and procedures for the relocation or transfer of hardware, software |
| DCS-05.2 | NA | MODERATE | DCS | Are policies and procedures for the secure transportation of physical media revi |
| DCS-06.2 | NO | WEAK | DCS | Is the assets' classification reviewed and updated at least annually or upon sig |
| DCS-10.2 | NO | WEAK | DCS | Are access control records retained periodically, as deemed appropriate by the o |
| DCS-16.1 | NA | MODERATE | DCS | Is business-critical equipment segregated from locations subject to a high proba |
| DCS-17.1 | NA | MODERATE | DCS | Are data center security metrics established, monitored and reported, to secure  |
| DCS-18.1 | NA | MODERATE | DCS | Are processes, procedures and technical measures defined, implemented and evalua |
| DSP-03.2 | NO | WEAK | DSP | Are inventories reviewed and updated at least annually or upon significant chang |
| DSP-20.1 | YES | MODERATE | DSP | Are processes, procedures, and technical measures defined, implemented, and eval |
| DSP-21.1 | NO | WEAK | DSP | Are processes, procedures and technical measures to prevent data poisoning in AI |
| DSP-22.1 | NO | WEAK | DSP | Are Privacy Enhancing Technologies (PET) used for training data informed by risk |
| DSP-23.1 | NO | WEAK | DSP | Is the consistency and conformity of training, fine-tuning or augmentation data  |
| DSP-23.2 | NO | WEAK | DSP | Is dataset versioning to ensure traceability implemented and are restrictions to |
| DSP-24.1 | NO | WEAK | DSP | Is training-data differentiation and relevance to the intended use of the AI Mod |
| GRC-07.2 | NO | WEAK | GRC | Are all relevant standards, regulations, legal/contractual and statutory require |
| GRC-09.1 | NO | WEAK | GRC | Are policies and procedures defined, documented, and enforced for the acceptable |
| GRC-09.2 | NO | WEAK | GRC | Is effectiveness of the acceptable use of AI services policies and procedures ev |
| GRC-10.1 | NO | WEAK | GRC | Is an AI Impact Assessment process  and its criteria to regularly evaluate the e |
| GRC-11.1 | YES | MODERATE | GRC | Are AI systems, models, datasets & algorithms regularly evaluated for bias and f |
| GRC-12.1 | NO | WEAK | GRC | Is an ethics committee established to review AI applications, ensuring alignment |
| GRC-13.1 | NO | WEAK | GRC | Is the degree of explainability required for the AI Services established, docume |
| GRC-14.1 | NO | WEAK | GRC | Is the degree of explainability of the AI Services evaluated, documented, and co |
| GRC-15.1 | YES | STRONG | GRC | Are processes, procedures, and technical measures to ensure human oversight and  |
| HRS-14.1 | NO | WEAK | HRS | Are the policies and procedures defining the AI training program for all relevan |
| HRS-14.2 | NO | WEAK | HRS | Are regular training updates given to personnel based on their roles? |
| HRS-15.1 | NO | WEAK | HRS | Are the policies and procedures on the acceptable use of AI technologies within  |
| IAM-13.2 | NO | WEAK | IAM | Are digital certificates or alternatives adopted that achieve an equivalent leve |
| IAM-17.1 | YES | MODERATE | IAM | Are roles for access when allowing model output modification of AI-generated out |
| IAM-18.1 | YES | MODERATE | IAM | Are agents' access to the tools and plugins necessary for the activity or use ca |
| I&S-01.1 | NO | WEAK | I&S | Has the organization established, documented, approved, communicated, applied, e |
| I&S-01.2 | NO | WEAK | I&S | Are these policies and procedures reviewed and updated at least annually, or upo |
| I&S-02.1 | NO | WEAK | I&S | Are availability, quality and the adequate capacity of resources, being planned  |
| I&S-03.1 | NO | WEAK | I&S | Are communications between environments, services, and applications being monito |
| I&S-03.2 | NO | WEAK | I&S | Are these configurations reviewed at least annually and supported by a documente |
| I&S-04.1 | NA | MODERATE | I&S | Are the host and guest OS, hypervisor, or infrastructure control plane, being ha |
| I&S-05.1 | NO | WEAK | I&S | Are production and non-production environments separated, to reduce the risk of  |
| I&S-05.2 | NO | WEAK | I&S | Is production data sanitized or protected before any authorized non-production u |
| I&S-06.1 | YES | MODERATE | I&S | Are applications and infrastructures designed, developed, deployed and configure |
| I&S-07.1 | NO | NONE | I&S | Are secure and encrypted communication channels used when migrating servers, ser |
| I&S-07.2 | NO | NONE | I&S | Are such channels including only up-to-date and approved protocols? |
| I&S-08.1 | NO | WEAK | I&S | Are high-risk environments based on data sensitivity, threat exposure, and busin |
| I&S-09.1 | NO | WEAK | I&S | Are processes, procedures, and defense-in-depth techniques for the protection, d |
| LOG-14.1 | NO | WEAK | LOG | Are processes and technical measures for reporting monitoring system anomalies a |
| LOG-14.2 | NO | WEAK | LOG | Are accountable parties immediately notified about anomalies and failures? |
| LOG-15.1 | NO | WEAK | LOG | Are all input events (content and metadata) logged and monitored to enable audit |
| LOG-16.1 | NO | WEAK | LOG | Are all output events (content and metadata) logged and monitored to enable audi |
| MDS-01.1 | NO | WEAK | MDS | Are processes, procedures, and technical measures defined, implemented, and eval |
| MDS-01.2 | NO | WEAK | MDS | Are policies, procedures and technical measures to address new security threats  |
| MDS-02.1 | NO | WEAK | MDS | Are processes, procedures, and technical measures defined, implemented, and eval |
| MDS-02.2 | NO | WEAK | MDS | Are policies, procedures and technical measures to address model artifact scanni |
| MDS-03.1 | NO | WEAK | MDS | Are processes and procedures defined, implemented, enforced, and evaluated for d |
| MDS-03.2 | NO | WEAK | MDS | Is the model documentation regularly reviewed and updated? |
| MDS-04.1 | NO | WEAK | MDS | Are baseline requirements for Model documentation established and implemented? |
| MDS-05.1 | NO | WEAK | MDS | Are processes, procedures, and technical measures defined, implemented, and eval |
| MDS-06.1 | NO | WEAK | MDS | Are processes and technical measures defined, implemented, and evaluated to regu |
| MDS-07.1 | NO | WEAK | MDS | Are processes, procedures, and technical measures defined, implemented, and eval |
| MDS-08.1 | NO | WEAK | MDS | Are checksums regularly calculated and compared using cryptographic hashes of mo |
| MDS-08.2 | NO | WEAK | MDS | Are these measures applied at least annually based on the level of risk, or afte |
| MDS-09.1 | NO | WEAK | MDS | Are models signed cryptographically and are signatures verified to ensure model  |
| MDS-10.1 | NO | WEAK | MDS | Are processes, procedures, and technical measures defined, implemented, and eval |
| MDS-11.1 | NO | WEAK | MDS | Is a risk-based evaluation of the model and model serving infrastructure for mod |
| MDS-11.2 | NO | WEAK | MDS | Are measures defined and implemented to mitigate model and model serving infrast |
| MDS-12.1 | NO | WEAK | MDS | Are processes established to evaluate the risk associated with open models? |
| MDS-12.2 | NO | WEAK | MDS | Are risk factors periodically reviewed, and is a process implemented to monitor  |
| MDS-13.1 | NO | WEAK | MDS | Are secure model formats and processes for AI model serialization adopted where  |
| SEF-08.2 | NO | WEAK | SEF | Are material security breaches including any relevant supply chain  breaches, as |
| SEF-09.1 | NO | WEAK | SEF | Is a secure repository of security incident records established and  maintained? |
| SEF-09.2 | NO | WEAK | SEF | Are the incident records regularly reviewed to identify patterns, root  causes,  |
| SEF-10.1 | NO | WEAK | SEF | Are points of contact maintained for applicable regulation authorities,  nationa |
| SEF-10.2 | NO | WEAK | SEF | Are the points of contact reviewed and updated at least annually? |
| STA-02.2 | NO | WEAK | STA | Are policies and procedures for applying the Shared Security Responsibility Mode |
| STA-09.2 | NO | WEAK | STA | Is the Bill of Material reviewed and updated at least annually or upon significa |
| STA-15.1 | NO | WEAK | STA | Are the organization's service providers' IT governance policies and procedures  |
| STA-16.1 | NO | WEAK | STA | Is a process for conducting risk-based security assessments of the  supply chain |
| TVM-04.2 | NO | WEAK | TVM | Are threat models built according to industry best practices to inform the risk  |
| TVM-11.1 | YES | MODERATE | TVM | Are processes defined and implemented for tracking and reporting vulnerability i |
| TVM-12.1 | NO | WEAK | TVM | Are metrics established, monitored, and reported for vulnerability identificatio |
| TVM-13.1 | YES | STRONG | TVM | Are processes, procedures, and technical measures to apply guardrails to the AI  |
| TVM-13.2 | NO | WEAK | TVM | Are guardrails continuously evaluated for changes in regulatory requirements and |
