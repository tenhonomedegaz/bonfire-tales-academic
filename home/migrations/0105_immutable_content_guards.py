from django.db import migrations


SQL = """
CREATE FUNCTION bonfire_reject_revision_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Sealed content is immutable';
END;
$$;
CREATE TRIGGER content_revision_immutable BEFORE UPDATE OR DELETE ON home_tbcontentrevision
FOR EACH ROW EXECUTE FUNCTION bonfire_reject_revision_mutation();
CREATE TRIGGER ruleset_immutable BEFORE UPDATE OR DELETE ON home_tbruleset
FOR EACH ROW EXECUTE FUNCTION bonfire_reject_revision_mutation();
CREATE TRIGGER ruleset_entry_immutable BEFORE UPDATE OR DELETE ON home_tbrulesetcontent
FOR EACH ROW EXECUTE FUNCTION bonfire_reject_revision_mutation();
CREATE FUNCTION bonfire_validate_ruleset_entry() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected text; actual text; content_identity text;
BEGIN
  SELECT manifest ->> NEW.identity INTO expected FROM home_tbruleset WHERE id = NEW.ruleset_id;
  SELECT checksum, identity INTO actual, content_identity FROM home_tbcontentrevision WHERE id = NEW.revision_id;
  IF expected IS NULL OR actual IS DISTINCT FROM expected OR content_identity IS DISTINCT FROM NEW.identity THEN
    RAISE EXCEPTION 'Entry does not match sealed ruleset manifest';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER ruleset_entry_validate BEFORE INSERT ON home_tbrulesetcontent
FOR EACH ROW EXECUTE FUNCTION bonfire_validate_ruleset_entry();
"""

REVERSE = """
DROP TRIGGER ruleset_entry_validate ON home_tbrulesetcontent;
DROP FUNCTION bonfire_validate_ruleset_entry();
DROP TRIGGER ruleset_entry_immutable ON home_tbrulesetcontent;
DROP TRIGGER ruleset_immutable ON home_tbruleset;
DROP TRIGGER content_revision_immutable ON home_tbcontentrevision;
DROP FUNCTION bonfire_reject_revision_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [('home', '0104_immutable_content_rulesets')]
    operations = [migrations.RunSQL(SQL, REVERSE)]
